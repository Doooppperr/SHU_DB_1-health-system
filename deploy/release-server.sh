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

ln -sfn "$release" /opt/healthdoc/current.new
mv -Tf /opt/healthdoc/current.new /opt/healthdoc/current

test "$(readlink -f /var/www/html)" = /var/www/html
find /var/www/html -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
cp -a "$release/frontend/dist/." /var/www/html/
chown -R root:www-data /var/www/html
find /var/www/html -type d -exec chmod 755 {} +
find /var/www/html -type f -exec chmod 644 {} +

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
echo "Released $release_id successfully."
