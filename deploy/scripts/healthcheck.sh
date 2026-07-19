#!/bin/bash
# ============================================================================
# OPC-Agents 健康检查脚本
# 作用：周期性检查官网、网关、支撑服务可用性，连续失败 3 次告警到企业微信
# 关联文档：docs/architecture/DEPLOYMENT_ARCHITECTURE.md §3.4 / §7.2
# 部署位置：/opt/healthcheck/healthcheck.sh（cron 每 1 分钟执行）
# 硬约束 H8：webhook URL 必须从环境变量 WECOM_WEBHOOK_URL 读取，禁止明文
# 退出码：全部通过 0，任一失败 1
# ============================================================================

set -euo pipefail

# ---------- 常量 ----------
readonly WEBSITE_URL="https://promiselink.cn/"
readonly GATEWAY_HEALTH_URL="https://gateway.promiselink.cn/health"
readonly GATEWAY_API_HEALTH_URL="https://gateway.promiselink.cn/api/v1/health"
readonly PG_HOST="127.0.0.1"
readonly PG_PORT="5432"
readonly REDIS_HOST="127.0.0.1"
readonly REDIS_PORT="6379"

# 连续失败阈值（DEPLOYMENT_ARCHITECTURE.md §3.4）
readonly FAIL_THRESHOLD=3

# 状态持久化目录（用于记录连续失败次数）
readonly STATE_DIR="/var/lib/opc-healthcheck"
readonly STATE_FILE="${STATE_DIR}/fail-count.txt"

# ---------- 颜色（不使用 emoji） ----------
readonly COLOR_RED='\033[0;31m'
readonly COLOR_GREEN='\033[0;32m'
readonly COLOR_YELLOW='\033[1;33m'
readonly COLOR_RESET='\033[0m'

# ---------- 日志 ----------
log() {
    local level="$1"
    shift
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    local color=""
    case "${level}" in
        OK)   color="${COLOR_GREEN}" ;;
        FAIL) color="${COLOR_RED}" ;;
        WARN) color="${COLOR_YELLOW}" ;;
    esac
    printf "[%s] [%b%s%b] %s\n" "$ts" "$color" "${level}" "$COLOR_RESET" "$*"
}

# ---------- HTTP 健康检查 ----------
# 用法：check_http <name> <url> <expected_code>
check_http() {
    local name="$1"
    local url="$2"
    local expected="$3"

    local http_code body
    http_code="$(curl -s -o /tmp/healthcheck-body -w '%{http_code}' \
        --max-time 10 --connect-timeout 5 -L "${url}" 2>/dev/null || echo "000")"

    if [[ "${http_code}" == "${expected}" ]]; then
        log OK "${name} ${url} -> HTTP ${http_code}"
        return 0
    fi

    log FAIL "${name} ${url} -> HTTP ${http_code}（期望 ${expected}）"
    return 1
}

# ---------- TCP 连通性检查 ----------
# 用法：check_tcp <name> <host> <port>
check_tcp() {
    local name="$1"
    local host="$2"
    local port="$3"

    # 优先用 nc（轻量）；缺失则用 bash 内置 /dev/tcp
    if command -v nc >/dev/null 2>&1; then
        if nc -z -w 5 "${host}" "${port}" >/dev/null 2>&1; then
            log OK "${name} ${host}:${port} TCP 连通"
            return 0
        fi
        log FAIL "${name} ${host}:${port} TCP 不通"
        return 1
    fi

    if (echo > "/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
        log OK "${name} ${host}:${port} TCP 连通"
        return 0
    fi
    log FAIL "${name} ${host}:${port} TCP 不通"
    return 1
}

# ---------- 企业微信告警 ----------
# 硬约束 H8：webhook URL 仅从环境变量读取
send_alert() {
    local message="$1"

    local webhook_url
    webhook_url="${WECOM_WEBHOOK_URL:-}"

    if [[ -z "${webhook_url}" ]]; then
        log WARN "WECOM_WEBHOOK_URL 未配置，跳过企业微信告警"
        return 0
    fi

    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"

    # 构造企业微信 text 消息体
    local payload
    payload="$(cat <<EOF
{
  "msgtype": "text",
  "text": {
    "content": "[OPC-Agents 健康检查告警]\\n时间: ${ts}\\n服务器: 47.116.219.15\\n详情: ${message}"
  }
}
EOF
)"

    local http_code
    http_code="$(curl -s -o /tmp/wecom-alert-response -w '%{http_code}' \
        -X POST -H 'Content-Type: application/json' \
        -d "${payload}" \
        --max-time 10 \
        "${webhook_url}" 2>/dev/null || echo "000")"

    if [[ "${http_code}" == "200" ]]; then
        log OK "企业微信告警已发送"
    else
        log FAIL "企业微信告警发送失败 (HTTP ${http_code})"
    fi
}

# ---------- 状态持久化 ----------
# 记录当前累计失败次数（仅在所有检查完成后调用一次）
init_state() {
    mkdir -p "${STATE_DIR}" 2>/dev/null || true
    if [[ ! -f "${STATE_FILE}" ]]; then
        echo "0" > "${STATE_FILE}"
    fi
}

read_fail_count() {
    cat "${STATE_FILE}" 2>/dev/null || echo "0"
}

write_fail_count() {
    local count="$1"
    echo "${count}" > "${STATE_FILE}" 2>/dev/null || true
}

# ---------- 主流程 ----------
main() {
    init_state

    local failures=0
    local fail_details=""

    # 依次执行 5 项检查
    if ! check_http "官网"            "${WEBSITE_URL}"            "200"; then
        failures=$((failures + 1))
        fail_details="${fail_details}官网首页不可用; "
    fi

    if ! check_http "网关健康检查"    "${GATEWAY_HEALTH_URL}"     "200"; then
        failures=$((failures + 1))
        fail_details="${fail_details}gateway.promiselink.cn/health 不可用; "
    fi

    if ! check_http "网关 API 健康"   "${GATEWAY_API_HEALTH_URL}" "200"; then
        failures=$((failures + 1))
        fail_details="${fail_details}gateway.promiselink.cn/api/v1/health 不可用; "
    fi

    if ! check_tcp  "PostgreSQL"      "${PG_HOST}"    "${PG_PORT}"; then
        failures=$((failures + 1))
        fail_details="${fail_details}PostgreSQL ${PG_HOST}:${PG_PORT} 不可达; "
    fi

    if ! check_tcp  "Redis"           "${REDIS_HOST}" "${REDIS_PORT}"; then
        failures=$((failures + 1))
        fail_details="${fail_details}Redis ${REDIS_HOST}:${REDIS_PORT} 不可达; "
    fi

    # 状态机：连续失败计数 + 告警
    local prev_count curr_count
    prev_count="$(read_fail_count)"

    if [[ ${failures} -eq 0 ]]; then
        # 全部通过：清零失败计数
        if [[ ${prev_count} -gt 0 ]]; then
            log OK "全部检查已恢复（此前连续失败 ${prev_count} 次）"
            # 可选：发送恢复通知（不强制）
            if [[ ${prev_count} -ge ${FAIL_THRESHOLD} ]]; then
                send_alert "所有端点已恢复正常（此前连续失败 ${prev_count} 次）"
            fi
        fi
        write_fail_count 0
        log OK "健康检查全部通过"
        exit 0
    fi

    # 有失败：累加计数
    curr_count=$((prev_count + 1))
    write_fail_count "${curr_count}"

    log WARN "本次失败 ${failures} 项；累计连续失败 ${curr_count} 次（阈值 ${FAIL_THRESHOLD}）"
    log WARN "失败详情: ${fail_details}"

    if [[ ${curr_count} -ge ${FAIL_THRESHOLD} ]]; then
        send_alert "连续 ${curr_count} 次检查失败（本次失败 ${failures} 项）。详情: ${fail_details}"
    fi

    exit 1
}

main "$@"
