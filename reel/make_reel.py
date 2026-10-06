"""
Builds the Facebook Reel that advertises the site: reel/congress-report-card-reel.mp4
(1080×1920, 22 seconds, H.264 with the background music from make_music.py).

  pip install imageio-ffmpeg numpy
  npm install
  python reel/make_reel.py

The numbers in the video are counted from site/data/members.js with the same grading as the
site, so run this again after a data update to refresh them. The animation itself is
reel/reel.html; open that file in a browser to preview it.
"""
import collections
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import build_pages  # noqa: E402
import make_music  # noqa: E402

FPS = 30
OUT = HERE / "congress-report-card-reel.mp4"


def stats():
    text = build_pages.DATA_FILE.read_text(encoding="utf-8")
    members = json.loads(text[text.index("{"):].rstrip().rstrip(";"))["members"]
    build_pages.compute_grades(members)
    grades = collections.Counter(m["grade"][0] for m in members)
    return {
        "members": len(members),
        "missed": sum(m["votes"]["missed"] for m in members),
        "missed50": sum(1 for m in members if m["votes"]["missed"] >= 50),
        "grades": {letter: grades[letter] for letter in "ABCDF"},
    }


def main():
    numbers = stats()
    print(numbers)
    (HERE / "stats.js").write_text(f"window.REEL_STATS = {json.dumps(numbers)};\n", encoding="utf-8")

    make_music.main()

    with tempfile.TemporaryDirectory() as frames:
        subprocess.run(["node", str(HERE / "render.js"), frames, str(FPS)], check=True, cwd=HERE.parent)
        subprocess.run([
            imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
            "-framerate", str(FPS), "-i", str(Path(frames) / "f_%04d.png"),
            "-i", str(make_music.OUT),
            "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT),
        ], check=True)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
