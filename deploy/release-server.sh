#!/usr/bin/env bash
set -euo pipefail

archive=${1:-}
release_id=${2:-}
demo_database=${3:-}

if [[ ! "$archive" =~ ^/home/[^/]+/healthdoc-app-[0-9]{8}T[0-9]{6}Z\.tar\.gz$ ]]; then
    echo "Refusing unexpected archive path: $archive" >&2
    exit 2
fi
if [[ ! "$release_id" =~ ^[0-9]{8}T[0-9]{6}Z$ ]]; then
    echo "Invalid release id: $release_id" >&2
    exit 2
fi
if [[ ! -f "$archive" ]]; then
    echo "Release archive not found: $archive" >&2
    exit 2
fi
if [[ -n "$demo_database" ]]; then
    if [[ ! "$demo_database" =~ ^/home/[^/]+/healthdoc-demo-[0-9]{8}T[0-9]{6}Z\.db$ ]]; then
        echo "Refusing unexpected demo database path: $demo_database" >&2
        exit 2
    fi
    if [[ ! -f "$demo_database" ]]; then
        echo "Demo database snapshot not found: $demo_database" >&2
        exit 2
    fi
fi

release="/opt/healthdoc/releases/$release_id"
previous=$(readlink -f /opt/healthdoc/current 2>/dev/null || true)
env_file=/etc/healthdoc/healthdoc.env
rag_root=/var/lib/healthdoc/rag
env_backup=$(mktemp /tmp/healthdoc-env.XXXXXX)
trap 'rm -f "$env_backup"' EXIT

if [[ ! -f "$env_file" ]]; then
    echo "Production environment file is missing: $env_file" >&2
    exit 2
fi
cp -p "$env_file" "$env_backup"

upsert_env() {
    local key=$1
    local value=$2
    if grep -q "^${key}=" "$env_file"; then
        sed -i "s|^${key}=.*$|${key}=${value}|" "$env_file"
    else
        printf '%s=%s\n' "$key" "$value" >>"$env_file"
    fi
}

if [[ -e "$release" ]]; then
    echo "Release already exists: $release" >&2
    exit 2
fi

install -d -o root -g root -m 755 "$release"
tar -xzf "$archive" -C "$release"
test -f "$release/backend/wsgi.py"
test -f "$release/frontend/dist/index.html"

/opt/healthdoc/venv/bin/python -m pip install -r "$release/backend/requirements.txt"
/opt/healthdoc/venv/bin/python -m pip check

database_backup=""
wait_for_database() {
    for _ in $(seq 1 60); do
        if (echo >/dev/tcp/127.0.0.1/5432) >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

restore_database_backup() {
    if [[ -z "$database_backup" || ! -f "$database_backup" ]]; then
        return 0
    fi
    docker stop healthdoc-gaussdb >/dev/null || true
    failed_database="/var/backups/healthdoc/$release_id/opengauss.failed"
    if [[ -e "$failed_database" ]]; then
        echo "Refusing to overwrite failed database snapshot: $failed_database" >&2
        return 1
    fi
    mv /var/lib/healthdoc/opengauss "$failed_database"
    tar -C /var/lib/healthdoc -xzf "$database_backup"
    docker start healthdoc-gaussdb >/dev/null
    wait_for_database
}

if [[ -n "$demo_database" ]]; then
    backup_root="/var/backups/healthdoc/$release_id"
    install -d -o root -g root -m 700 "$backup_root"
    install -m 600 /etc/healthdoc/healthdoc.env "$backup_root/healthdoc.env"
    if [[ -d /var/lib/healthdoc/uploads ]]; then
        tar -C /var/lib/healthdoc -czf "$backup_root/uploads.tar.gz" uploads
        chmod 600 "$backup_root/uploads.tar.gz"
    fi

    systemctl stop healthdoc.service
    docker stop healthdoc-gaussdb >/dev/null
    database_backup="$backup_root/opengauss.tar.gz"
    tar -C /var/lib/healthdoc -czf "$database_backup" opengauss
    chmod 600 "$database_backup"
    docker start healthdoc-gaussdb >/dev/null

    if ! wait_for_database; then
        echo "openGauss did not become ready after backup." >&2
        exit 1
    fi

    set -a
    # shellcheck disable=SC1091
    source /etc/healthdoc/healthdoc.env
    set +a
    if [[ -z "${DATABASE_URL:-}" ]]; then
        echo "DATABASE_URL is missing from the server environment file." >&2
        exit 1
    fi
    export TARGET_DATABASE_URL="$DATABASE_URL"
    if ! (
        cd "$release/backend"
        /opt/healthdoc/venv/bin/python scripts/migrate_sqlite_to_gaussdb.py \
            --source "$demo_database" --replace
    ); then
        echo "Demo database import failed; restoring the pre-release database." >&2
        unset TARGET_DATABASE_URL DATABASE_URL
        restore_database_backup
        systemctl start healthdoc.service
        exit 1
    fi
    unset TARGET_DATABASE_URL DATABASE_URL
    rm -f "$demo_database"
fi

install -d -o healthdoc -g www-data -m 750 \
    "$rag_root" "$rag_root/qdrant" "$rag_root/models" \
    "$rag_root/cache" "$rag_root/huggingface"

if grep -Eiq '^RAG_ENABLED=(1|true|yes|on)$' "$env_file"; then
    systemctl stop healthdoc.service
fi

upsert_env RAG_ENABLED 1
upsert_env RAG_RUNTIME_PATH "$rag_root"
upsert_env RAG_STORAGE_PATH "$rag_root/qdrant"
upsert_env RAG_MODEL_CACHE_PATH "$rag_root/models"

set +e
runuser -u healthdoc -- env \
    HOME=/var/lib/healthdoc \
    XDG_CACHE_HOME="$rag_root/cache" \
    HF_HOME="$rag_root/huggingface" \
    RAG_RUNTIME_PATH="$rag_root" \
    RAG_STORAGE_PATH="$rag_root/qdrant" \
    RAG_MODEL_CACHE_PATH="$rag_root/models" \
    /opt/healthdoc/venv/bin/python "$release/backend/scripts/rag_sync.py" sync
rag_sync_status=$?
set -e
if [[ "$rag_sync_status" != 0 ]]; then
    cp -p "$env_backup" "$env_file"
    rm -rf "$release"
    rm -f "$env_backup"
    if [[ -n "$database_backup" && -f "$database_backup" ]]; then
        restore_database_backup
    fi
    systemctl start healthdoc.service
    if [[ -n "$demo_database" ]]; then
        rm -f "$demo_database"
    fi
    echo "RAG sync failed; the current release, environment and database were restored." >&2
    exit "$rag_sync_status"
fi

ln -sfn "$release" /opt/healthdoc/current.new
mv -Tf /opt/healthdoc/current.new /opt/healthdoc/current

test "$(readlink -f /var/www/html)" = /var/www/html
find /var/www/html -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
cp -a "$release/frontend/dist/." /var/www/html/
chown -R root:www-data /var/www/html
find /var/www/html -type d -exec chmod 755 {} +
find /var/www/html -type f -exec chmod 644 {} +

install -o root -g root -m 644 \
    "$release/deploy/healthdoc.service" /etc/systemd/system/healthdoc.service
systemctl daemon-reload
systemctl restart healthdoc.service
healthy=0
for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:5050/api/health >/dev/null; then
        healthy=1
        break
    fi
    sleep 1
done

if [[ "$healthy" != 1 ]]; then
    journalctl -u healthdoc.service -n 80 --no-pager >&2 || true
    systemctl stop healthdoc.service || true
    if [[ -n "$database_backup" && -f "$database_backup" ]]; then
        restore_database_backup
    fi
    cp -p "$env_backup" "$env_file"
    if [[ -n "$previous" && -d "$previous" ]]; then
        ln -sfn "$previous" /opt/healthdoc/current.rollback
        mv -Tf /opt/healthdoc/current.rollback /opt/healthdoc/current
        find /var/www/html -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
        cp -a "$previous/frontend/dist/." /var/www/html/
        chown -R root:www-data /var/www/html
        systemctl restart healthdoc.service
    fi
    echo "Health check failed; the previous release was restored." >&2
    exit 1
fi

rm -f "$archive"
if [[ -n "$demo_database" ]]; then
    rm -f "$demo_database"
fi
rm -f "$env_backup"
echo "Released $release_id successfully."
