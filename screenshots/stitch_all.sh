#!/usr/bin/env bash
set -euo pipefail

# Timing: each screenshot remains visible for 0.6s.
DISPLAY_DUR=0.6
# Crossfade overlap between consecutive screenshots.
FADE_DUR=0.24

mapfile -t frames < <(find . -maxdepth 1 -type f -name 'Screenshot_*.png' -printf '%f\n' | sort)

if [[ ${#frames[@]} -lt 2 ]]; then
  echo "Need at least 2 files matching Screenshot_*.png"
  exit 1
fi

inputs=()
filter=""
for i in "${!frames[@]}"; do
  inputs+=( -loop 1 -t "$DISPLAY_DUR" -i "${frames[$i]}" )
  filter+="[$i:v]scale=960:-1:flags=lanczos,format=rgba,setsar=1[v$i];"
done

# Chain fade transitions: [v0][v1] -> [x1], then [x1][v2] -> [x2], ...
for ((i=1; i<${#frames[@]}; i++)); do
  offset=$(awk -v i="$i" -v d="$DISPLAY_DUR" -v f="$FADE_DUR" 'BEGIN { printf "%.6f", i*(d-f) }')
  if [[ $i -eq 1 ]]; then
    filter+="[v0][v1]xfade=transition=fade:duration=$FADE_DUR:offset=$offset[x1];"
  else
    prev=$((i-1))
    filter+="[x$prev][v$i]xfade=transition=fade:duration=$FADE_DUR:offset=$offset[x$i];"
  fi
done

last=$(( ${#frames[@]} - 1 ))

ffmpeg -y "${inputs[@]}" \
  -filter_complex "$filter[x$last]fps=10,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5" \
  -loop 0 stitched.gif

echo "Created stitched.gif from ${#frames[@]} screenshots with smooth fades."