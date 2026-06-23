#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${ROOT_DIR}/data"
ARCHIVE="${DATA_DIR}/GSE278603_RAW.tar"
SAMPLE="GSM9046244_Embryo_E7.5_stereo_rep2.h5ad"
URL="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE278nnn/GSE278603/suppl/GSE278603_RAW.tar"

mkdir -p "${DATA_DIR}"

if [[ ! -f "${ARCHIVE}" ]]; then
  echo "Downloading GSE278603_RAW.tar from GEO. This file is about 803 MB."
  curl -L -C - --fail --progress-bar -o "${ARCHIVE}" "${URL}"
else
  echo "Archive already exists: ${ARCHIVE}"
fi

if [[ ! -f "${DATA_DIR}/${SAMPLE}" ]]; then
  echo "Extracting lightweight demo sample: ${SAMPLE}"
  tar -xvf "${ARCHIVE}" -C "${DATA_DIR}" "${SAMPLE}"
else
  echo "Sample already exists: ${DATA_DIR}/${SAMPLE}"
fi

echo "Ready: ${DATA_DIR}/${SAMPLE}"
