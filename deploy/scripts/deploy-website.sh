#!/bin/bash
# ============================================================================
# OPC-Agents 官网部署脚本
# 作用：将本地 website/ 静态文件与 deploy/nginx/ 配置同步到云端 47.116.219.15
# 关联文档：docs/architecture/DEPLOYMENT_ARCHITECTURE.md §5.2
# 用法：./deploy/scripts/deploy-website.sh [--staging|--production]
# 硬约束 H6：47.116.219.15 仅部署官网 + 网关 + 支撑服务
# 硬约束 H7：nginx 默认 server 仅服务静态文件，禁止 proxy_pass
# 硬约束 H8：本脚本不读写任何 API Key / 密码 / Token
# ============================================================================

set -euo pipefail

# ---------- 常量 ----------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly REMOTE_HOST="root@47.116.219.15"
readonly REMOTE_WWW_DIR="/var/www/html"
readonly REMOTE_SCRIPTS_DIR="/var/www/scripts"
readonly REMOTE_NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
readonly REMOTE_NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"
readonly WEBSITE_LOCAL_DIR="${REPO_ROOT}/website"
readonly NGINX_LOCAL_DIR="${REPO_ROOT}/deploy/nginx"
readonly HEALTH_URL="https://promiselink.cn/"

# 部署目标：production -> 线上服务器；staging -> 仅做 dry-run
readonly ENV_PRODUCTION="production"
readonly ENV_STAGING="staging"
DEPLOY_TARGET="${ENV_PRODUCTION}"

# ---------- 颜色（不使用 emoji） ----------
readonly COLOR_RED='\033[0;31m'
readonly COLOR_GREEN='\033[0;32m'
readonly COLOR_YELLOW='\033[1;33m'
readonly COLOR_BLUE='\033[0;34m'
readonly COLOR_RESET='\033[0m'

# ---------- 日志函数 ----------
log_info() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    printf "[%s] [%bINFO%b] %s\n" "$ts" "$COLOR_BLUE" "$COLOR_RESET" "$*"
}

log_ok() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    printf "[%s] [%bOK%b]   %s\n" "$ts" "$COLOR_GREEN" "$COLOR_RESET" "$*"
}

log_warn() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    printf "[%s] [%bWARN%b] %s\n" "$ts" "$COLOR_YELLOW" "$COLOR_RESET" "$*" >&2
}

log_fail() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    printf "[%s] [%bFAIL%b] %s\n" "$ts" "$COLOR_RED" "$COLOR_RESET" "$*" >&2
}

die() {
    log_fail "$*"
    exit 1
}

# ---------- 用法 ----------
usage() {
    cat <<EOF
用法: $0 [--staging|--production]
  --staging     仅做语法检查与 dry-run，不写入远端
  --production  部署到线上 47.116.219.15（默认）
  -h, --help    显示本帮助
EOF
    exit 1
}

# ---------- 参数解析 ----------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --staging)
                DEPLOY_TARGET="${ENV_STAGING}"
                ;;
            --production)
                DEPLOY_TARGET="${ENV_PRODUCTION}"
                ;;
            -h|--help)
                usage
                ;;
            *)
                log_warn "未知参数: $1"
                usage
                ;;
        esac
        shift
    done
}

# ---------- 前置检查 ----------
check_prerequisites() {
    log_info "前置检查"

    [[ -d "${WEBSITE_LOCAL_DIR}" ]] \
        || die "官网目录不存在: ${WEBSITE_LOCAL_DIR}"

    [[ -f "${WEBSITE_LOCAL_DIR}/index.html" ]] \
        || die "官网首页缺失: ${WEBSITE_LOCAL_DIR}/index.html"

    [[ -f "${WEBSITE_LOCAL_DIR}/styles.css" ]] \
        || die "官网样式缺失: ${WEBSITE_LOCAL_DIR}/styles.css"

    [[ -f "${WEBSITE_LOCAL_DIR}/404.html" ]] \
        || die "官网 404 页缺失: ${WEBSITE_LOCAL_DIR}/404.html"

    [[ -f "${NGINX_LOCAL_DIR}/nginx.conf" ]] \
        || die "nginx 主配置缺失: ${NGINX_LOCAL_DIR}/nginx.conf"

    [[ -d "${NGINX_LOCAL_DIR}/sites-available" ]] \
        || die "nginx sites-available 目录缺失"

    local conf
    for conf in default.conf promiselink.cn.conf gateway.promiselink.cn.conf; do
        [[ -f "${NGINX_LOCAL_DIR}/sites-available/${conf}" ]] \
            || die "nginx 站点配置缺失: ${conf}"
    done

    command -v rsync >/dev/null 2>&1 \
        || die "rsync 命令未安装，请执行 brew install rsync 或 apt-get install rsync"

    command -v ssh >/dev/null 2>&1 \
        || die "ssh 命令未安装"

    log_ok "本地文件齐全"
}

# ---------- Staging 检查（仅 dry-run） ----------
run_staging_checks() {
    log_info "Staging 模式：执行 dry-run，不写入远端"

    # rsync dry-run 检查 website 同步
    rsync -avzn --delete \
        --exclude='.DS_Store' \
        --exclude='__MACOSX' \
        "${WEBSITE_LOCAL_DIR}/" \
        "${REMOTE_HOST}:${REMOTE_WWW_DIR}/" \
        || die "rsync dry-run 失败"

    log_ok "rsync dry-run 通过"
    log_info "如需正式部署，请使用 --production 参数"
}

# ---------- 同步官网静态文件 ----------
sync_website() {
    log_info "同步官网静态文件到 ${REMOTE_HOST}:${REMOTE_WWW_DIR}/"

    # 在远端确保目录存在
    ssh -o StrictHostKeyChecking=accept-new "${REMOTE_HOST}" \
        "mkdir -p ${REMOTE_WWW_DIR} ${REMOTE_SCRIPTS_DIR}" \
        || die "远端目录创建失败"

    # rsync 同步（--delete 保证远端无残留旧文件）
    rsync -avz --delete \
        --exclude='.DS_Store' \
        --exclude='__MACOSX' \
        --exclude='.gitkeep' \
        "${WEBSITE_LOCAL_DIR}/" \
        "${REMOTE_HOST}:${REMOTE_WWW_DIR}/" \
        || die "rsync 同步官网文件失败"

    log_ok "官网静态文件已同步"
}

# ---------- 同步 nginx 配置 ----------
sync_nginx_configs() {
    log_info "同步 nginx 配置文件到 ${REMOTE_HOST}"

    # 主配置
    scp -q "${NGINX_LOCAL_DIR}/nginx.conf" \
        "${REMOTE_HOST}:/etc/nginx/nginx.conf" \
        || die "scp nginx.conf 失败"

    # 站点配置
    scp -q "${NGINX_LOCAL_DIR}/sites-available/"*.conf \
        "${REMOTE_HOST}:${REMOTE_NGINX_SITES_AVAILABLE}/" \
        || die "scp sites-available/*.conf 失败"

    log_ok "nginx 配置文件已上传"
}

# ---------- 远端：启用站点（创建软链接） ----------
enable_sites() {
    log_info "在远端创建 sites-enabled 软链接"

    ssh -o StrictHostKeyChecking=accept-new "${REMOTE_HOST}" bash <<'REMOTE_EOF'
set -euo pipefail
cd /etc/nginx/sites-enabled

ln -sf /etc/nginx/sites-available/default.conf                default
ln -sf /etc/nginx/sites-available/promiselink.cn.conf         promiselink.cn
ln -sf /etc/nginx/sites-available/gateway.promiselink.cn.conf gateway.promiselink.cn

ls -l /etc/nginx/sites-enabled/
REMOTE_EOF
    if [[ $? -ne 0 ]]; then
        die "远端创建软链接失败"
    fi

    log_ok "sites-enabled 软链接已创建"
}

# ---------- 远端：nginx 配置测试 + reload ----------
reload_nginx() {
    log_info "远端 nginx -t 测试配置"

    if ! ssh -o StrictHostKeyChecking=accept-new "${REMOTE_HOST}" 'nginx -t'; then
        die "nginx -t 测试失败，配置未生效"
    fi
    log_ok "nginx -t 通过"

    log_info "远端 nginx -s reload"
    if ! ssh -o StrictHostKeyChecking=accept-new "${REMOTE_HOST}" 'nginx -s reload'; then
        die "nginx -s reload 失败"
    fi
    log_ok "nginx 已平滑重载"
}

# ---------- 健康检查 ----------
run_healthcheck() {
    log_info "健康检查: ${HEALTH_URL}"

    local max_attempts=10
    local attempt=0
    local http_code

    while [[ $attempt -lt $max_attempts ]]; do
        attempt=$((attempt + 1))
        http_code="$(curl -s -o /dev/null -w '%{http_code}' \
            --max-time 10 \
            -L "${HEALTH_URL}" || echo "000")"

        if [[ "${http_code}" == "200" ]]; then
            log_ok "健康检查通过（HTTP ${http_code}，第 ${attempt} 次尝试）"
            return 0
        fi
        log_warn "第 ${attempt} 次尝试返回 HTTP ${http_code}，5 秒后重试..."
        sleep 5
    done

    die "健康检查失败：连续 ${max_attempts} 次未返回 200（最后状态：${http_code}）"
}

# ---------- 主流程 ----------
main() {
    parse_args "$@"
    log_info "OPC-Agents 官网部署开始（目标环境：${DEPLOY_TARGET}）"

    check_prerequisites

    if [[ "${DEPLOY_TARGET}" == "${ENV_STAGING}" ]]; then
        run_staging_checks
        log_ok "Staging dry-run 完成，未写入任何远端文件"
        exit 0
    fi

    sync_website
    sync_nginx_configs
    enable_sites
    reload_nginx
    run_healthcheck

    log_ok "官网部署成功完成"
    log_info "线上访问地址: ${HEALTH_URL}"
}

main "$@"
