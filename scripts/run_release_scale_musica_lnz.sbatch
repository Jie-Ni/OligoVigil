#!/bin/bash
#SBATCH --job-name=oligo3000
#SBATCH --partition=zen4_0768
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/scratch/fs201130/jn20658/oligosafetydb_remote/logs/oligo3000_%j.out
#SBATCH --error=/scratch/fs201130/jn20658/oligosafetydb_remote/logs/oligo3000_%j.err

set -euo pipefail

BASE=/scratch/fs201130/jn20658/oligosafetydb_remote
INPUT_TAR="$BASE/incoming/oligosafetydb_remote_input.tar"
OUT_DIR="$BASE/output/$SLURM_JOB_ID"
LOG_DIR="$BASE/logs"
mkdir -p "$OUT_DIR" "$LOG_DIR"

if mkdir -p "/local/$USER/oligosafetydb_$SLURM_JOB_ID" 2>/dev/null; then
  WORK_DIR="/local/$USER/oligosafetydb_$SLURM_JOB_ID"
elif [ -n "${TMPDIR:-}" ] && mkdir -p "$TMPDIR/oligosafetydb_$SLURM_JOB_ID" 2>/dev/null; then
  WORK_DIR="$TMPDIR/oligosafetydb_$SLURM_JOB_ID"
else
  WORK_DIR="$BASE/work_$SLURM_JOB_ID"
  mkdir -p "$WORK_DIR"
fi

stage_out() {
  set +e
  if [ -d "$WORK_DIR/data/generated" ]; then
    cp "$WORK_DIR"/data/generated/release_scale_3000* "$OUT_DIR"/ 2>/dev/null || true
    cp "$WORK_DIR"/data/generated/RELEASE_SCALE_3000_PRECURATION.md "$OUT_DIR"/ 2>/dev/null || true
    if [ -d "$WORK_DIR/data/generated/pmc_xml_cache" ]; then
      find "$WORK_DIR/data/generated/pmc_xml_cache" -name '*.xml' | wc -l > "$OUT_DIR/pmc_xml_cache_count.txt"
    fi
  fi
  cp "$LOG_DIR/oligo3000_${SLURM_JOB_ID}.out" "$OUT_DIR/" 2>/dev/null || true
  cp "$LOG_DIR/oligo3000_${SLURM_JOB_ID}.err" "$OUT_DIR/" 2>/dev/null || true
  if [[ "$WORK_DIR" == /local/* || "$WORK_DIR" == "${TMPDIR:-/none}"/* ]]; then
    rm -rf "$WORK_DIR"
  fi
}
trap stage_out EXIT

echo "job_id=$SLURM_JOB_ID"
echo "node=$(hostname)"
echo "work_dir=$WORK_DIR"
echo "started_at=$(date -Is)"
python3 --version

tar -xf "$INPUT_TAR" -C "$WORK_DIR"
cd "$WORK_DIR"

python3 -m py_compile \
  scripts/build_verified_batch1_packet.py \
  scripts/build_release_scale_packet.py \
  scripts/release_scale_packet_check.py \
  scripts/promote_curator_review.py

python3 scripts/build_release_scale_packet.py \
  --target 3000 \
  --max-offtarget 1000 \
  --pause-seconds 0.34 \
  --checkpoint-every 100 \
  --output-cards data/generated/RELEASE_SCALE_3000_PRECURATION.md

python3 scripts/release_scale_packet_check.py

cp data/generated/release_scale_3000* "$OUT_DIR"/
cp data/generated/RELEASE_SCALE_3000_PRECURATION.md "$OUT_DIR"/
find data/generated/pmc_xml_cache -name '*.xml' | wc -l > "$OUT_DIR/pmc_xml_cache_count.txt"

echo "finished_at=$(date -Is)"
echo "out_dir=$OUT_DIR"
