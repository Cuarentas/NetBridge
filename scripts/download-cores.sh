#!/usr/bin/env bash
# 下载主流核心二进制到 core/bin/
# 使用方法: ./scripts/download-cores.sh [platform]
# platform 可选: linux-amd64 | linux-arm64 | darwin-amd64 | darwin-arm64 | windows-amd64
# 默认自动检测当前平台

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="${ROOT}/core/bin"
mkdir -p "${BIN_DIR}"

detect_platform() {
  local os arch
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"
  case "${os}" in
    linux)  os="linux" ;;
    darwin) os="darwin" ;;
    mingw*|msys*|cygwin*) os="windows" ;;
    *) echo "Unsupported OS: ${os}"; exit 1 ;;
  esac
  case "${arch}" in
    x86_64|amd64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) echo "Unsupported arch: ${arch}"; exit 1 ;;
  esac
  echo "${os}-${arch}"
}

PLATFORM="${1:-$(detect_platform)}"
echo "==> Platform: ${PLATFORM}"

# ---------- sing-box ----------
SINGBOX_VERSION="1.11.0"   # 可按需更新
SINGBOX_URL=""
case "${PLATFORM}" in
  linux-amd64)   SINGBOX_URL="https://github.com/SagerNet/sing-box/releases/download/v${SINGBOX_VERSION}/sing-box-${SINGBOX_VERSION}-linux-amd64.tar.gz" ;;
  linux-arm64)   SINGBOX_URL="https://github.com/SagerNet/sing-box/releases/download/v${SINGBOX_VERSION}/sing-box-${SINGBOX_VERSION}-linux-arm64.tar.gz" ;;
  darwin-amd64)  SINGBOX_URL="https://github.com/SagerNet/sing-box/releases/download/v${SINGBOX_VERSION}/sing-box-${SINGBOX_VERSION}-darwin-amd64.tar.gz" ;;
  darwin-arm64)  SINGBOX_URL="https://github.com/SagerNet/sing-box/releases/download/v${SINGBOX_VERSION}/sing-box-${SINGBOX_VERSION}-darwin-arm64.tar.gz" ;;
  windows-amd64) SINGBOX_URL="https://github.com/SagerNet/sing-box/releases/download/v${SINGBOX_VERSION}/sing-box-${SINGBOX_VERSION}-windows-amd64.zip" ;;
  *) echo "sing-box: unsupported platform ${PLATFORM}"; ;;
esac

if [[ -n "${SINGBOX_URL}" ]]; then
  echo "==> Downloading sing-box ${SINGBOX_VERSION} ..."
  TMP="$(mktemp -d)"
  if [[ "${PLATFORM}" == windows-amd64 ]]; then
    curl -fsSL "${SINGBOX_URL}" -o "${TMP}/sing-box.zip"
    unzip -q "${TMP}/sing-box.zip" -d "${TMP}"
    cp "${TMP}/sing-box-${SINGBOX_VERSION}-windows-amd64/sing-box.exe" "${BIN_DIR}/sing-box.exe"
  else
    curl -fsSL "${SINGBOX_URL}" | tar -xz -C "${TMP}"
    # 解压后目录名可能带版本
    find "${TMP}" -name "sing-box" -type f -executable | head -1 | xargs -I{} cp {} "${BIN_DIR}/sing-box"
    chmod +x "${BIN_DIR}/sing-box"
  fi
  rm -rf "${TMP}"
  echo "    -> ${BIN_DIR}/sing-box"
fi

# ---------- mihomo (Clash Meta) ----------
# 版本号请根据官方 Release 更新
MIHOMO_VERSION="1.19.0"
MIHOMO_URL=""
case "${PLATFORM}" in
  linux-amd64)   MIHOMO_URL="https://github.com/MetaCubeX/mihomo/releases/download/v${MIHOMO_VERSION}/mihomo-linux-amd64-v${MIHOMO_VERSION}.gz" ;;
  linux-arm64)   MIHOMO_URL="https://github.com/MetaCubeX/mihomo/releases/download/v${MIHOMO_VERSION}/mihomo-linux-arm64-v${MIHOMO_VERSION}.gz" ;;
  darwin-amd64)  MIHOMO_URL="https://github.com/MetaCubeX/mihomo/releases/download/v${MIHOMO_VERSION}/mihomo-darwin-amd64-v${MIHOMO_VERSION}.gz" ;;
  darwin-arm64)  MIHOMO_URL="https://github.com/MetaCubeX/mihomo/releases/download/v${MIHOMO_VERSION}/mihomo-darwin-arm64-v${MIHOMO_VERSION}.gz" ;;
  windows-amd64) MIHOMO_URL="https://github.com/MetaCubeX/mihomo/releases/download/v${MIHOMO_VERSION}/mihomo-windows-amd64-v${MIHOMO_VERSION}.zip" ;;
esac

if [[ -n "${MIHOMO_URL}" ]]; then
  echo "==> Downloading mihomo ${MIHOMO_VERSION} ..."
  TMP="$(mktemp -d)"
  if [[ "${PLATFORM}" == windows-amd64 ]]; then
    curl -fsSL "${MIHOMO_URL}" -o "${TMP}/mihomo.zip"
    unzip -q "${TMP}/mihomo.zip" -d "${TMP}"
    find "${TMP}" -name "mihomo*.exe" | head -1 | xargs -I{} cp {} "${BIN_DIR}/mihomo.exe"
  else
    curl -fsSL "${MIHOMO_URL}" -o "${TMP}/mihomo.gz"
    gunzip -c "${TMP}/mihomo.gz" > "${BIN_DIR}/mihomo"
    chmod +x "${BIN_DIR}/mihomo"
  fi
  rm -rf "${TMP}"
  echo "    -> ${BIN_DIR}/mihomo"
fi

# ---------- Xray ----------
XRAY_VERSION="25.3.6"
XRAY_URL=""
case "${PLATFORM}" in
  linux-amd64)   XRAY_URL="https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-linux-64.zip" ;;
  linux-arm64)   XRAY_URL="https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-linux-arm64-v8a.zip" ;;
  darwin-amd64)  XRAY_URL="https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-macos-64.zip" ;;
  darwin-arm64)  XRAY_URL="https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-macos-arm64-v8a.zip" ;;
  windows-amd64) XRAY_URL="https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-windows-64.zip" ;;
esac

if [[ -n "${XRAY_URL}" ]]; then
  echo "==> Downloading Xray ${XRAY_VERSION} ..."
  TMP="$(mktemp -d)"
  curl -fsSL "${XRAY_URL}" -o "${TMP}/xray.zip"
  unzip -q "${TMP}/xray.zip" -d "${TMP}"
  if [[ "${PLATFORM}" == windows-amd64 ]]; then
    cp "${TMP}/xray.exe" "${BIN_DIR}/xray.exe"
  else
    cp "${TMP}/xray" "${BIN_DIR}/xray"
    chmod +x "${BIN_DIR}/xray"
  fi
  rm -rf "${TMP}"
  echo "    -> ${BIN_DIR}/xray"
fi

echo ""
echo "==> Done. Binaries in ${BIN_DIR}:"
ls -lh "${BIN_DIR}"
echo ""
echo "提示：版本号可能已更新，请到对应 GitHub Releases 页面确认最新版本并修改本脚本。"
