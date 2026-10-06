"""
Writes the reel's background music: reel/music.wav (22 seconds, stereo).

The track is synthesized here from scratch, so there is nothing to license. It is a simple
100 bpm bed in A minor that ends on C major: a soft pad and bass at first, a plucked arpeggio
from the second scene, and drums from the third. make_reel.py runs this for you.

  pip install numpy
  python reel/make_music.py
"""
import wave
from pathlib import Path

import numpy as np

RATE = 44100
SECONDS = 22.0
BEAT = 0.6  # 100 bpm
BAR = BEAT * 4
OUT = Path(__file__).resolve().parent / "music.wav"

# One chord per bar: (bass note, three chord notes), as MIDI note numbers.
AM, F, C, G = (45, (57, 60, 64)), (41, (53, 57, 60)), (36, (55, 60, 64)), (43, (55, 59, 62))
CHORDS = [AM, F, C, G, AM, F, C, G, C, C]
ARP = [(0, 0), (2, 0), (1, 0), (2, 0), (0, 12), (2, 0), (1, 0), (2, 0)]  # (chord note, shift)

rng = np.random.default_rng(1914)


def hz(note):
    return 440.0 * 2 ** ((note - 69) / 12)


def clock(length):
    return np.arange(int(length * RATE)) / RATE


def add(track, start, sound, gain=1.0):
    """Mixes a mono sound into a mono track at `start` seconds."""
    i = int(start * RATE)
    if i >= len(track):
        return
    sound = sound[:len(track) - i]
    track[i:i + len(sound)] += sound * gain


def pad_note(note, length):
    t = clock(length + 1.0)
    tone = sum(np.sin(2 * np.pi * hz(note) * d * t) for d in (0.997, 1.0, 1.003)) / 3
    tone += 0.25 * np.sin(2 * np.pi * hz(note) * 2 * t)
    return tone * np.minimum(1, t / 0.8) * np.minimum(1, (length + 1.0 - t) / 1.0)


def pluck(note, length=0.5):
    t = clock(length)
    tone = np.sin(2 * np.pi * hz(note) * t) + 0.35 * np.sin(2 * np.pi * hz(note) * 2 * t) \
        + 0.12 * np.sin(2 * np.pi * hz(note) * 3 * t)
    return tone * np.exp(-t * 9) * np.minimum(1, t / 0.004)


def bass_note(note, length=0.55):
    t = clock(length)
    tone = np.sin(2 * np.pi * hz(note) * t) + 0.3 * np.sin(2 * np.pi * hz(note) * 2 * t)
    return tone * np.exp(-t * 4) * np.minimum(1, t / 0.008)


def kick():
    t = clock(0.3)
    pitch = 45 + 90 * np.exp(-t * 35)
    return np.sin(2 * np.pi * np.cumsum(pitch) / RATE) * np.exp(-t * 14)


def noise_hit(length, decay, bright):
    """A burst of noise: bright=True for a hi-hat, False for a softer clap."""
    t = clock(length)
    noise = rng.standard_normal(len(t))
    if bright:
        noise = np.diff(noise, prepend=0)  # removes the low end
    else:
        noise = np.convolve(noise, np.ones(6) / 6, mode="same")
    return noise * np.exp(-t * decay)


def main():
    n = int(SECONDS * RATE)
    pad, bass, arp, drums = (np.zeros(n) for _ in range(4))

    for bar, (root, chord) in enumerate(CHORDS):
        at = bar * BAR
        for note in chord:
            add(pad, at, pad_note(note, BAR), 0.16)
        add(pad, at, pad_note(root + 12, BAR), 0.14)

        for eighth in range(8):
            when = at + eighth * BEAT / 2
            # Bass: once a bar at first, then a steady pulse.
            if eighth == 0 or (bar >= 3 and eighth % 2 == 0) or (bar >= 5 and eighth == 7):
                add(bass, when, bass_note(root), 0.5)
            # Arpeggio: comes in quietly in bar 2 and is at full volume from bar 4.
            if when >= 3.4 and bar < 9:
                which, shift = ARP[eighth]
                add(arp, when, pluck(chord[which] + 12 + shift), min(0.3, 0.1 + 0.05 * (bar - 1)))
            if bar >= 3 and bar < 9:
                if eighth % 2 == 0:
                    add(drums, when, kick(), 0.7)
                else:
                    add(drums, when, noise_hit(0.08, 60, True), 0.1)
                if bar >= 5 and eighth in (2, 6):
                    add(drums, when, noise_hit(0.2, 22, False), 0.22)

    # The arpeggio echoes to the left and right to give the track some width.
    def echo(track, delay, gain):
        out = np.zeros_like(track)
        shift = int(delay * RATE)
        out[shift:] = track[:-shift] * gain
        return out

    centre = pad + bass + drums
    left = centre + arp + echo(arp, BEAT * 0.75, 0.35)
    right = centre + arp * 0.8 + echo(arp, BEAT * 0.5, 0.4)
    mix = np.stack([left, right], axis=1)

    t = clock(SECONDS)[:n]
    fade = np.minimum(1, t / 0.4) * np.minimum(1, (SECONDS - t) / 2.0)
    mix = np.tanh(mix * 1.1) * fade[:, None]
    mix *= 0.7 / np.abs(mix).max()

    with wave.open(str(OUT), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes((mix * 32767).astype("<i2").tobytes())
    rms = 20 * np.log10(np.sqrt((mix ** 2).mean()))
    print(f"Wrote {OUT} (peak {20 * np.log10(np.abs(mix).max()):.1f} dBFS, average {rms:.1f} dBFS)")


if __name__ == "__main__":
    main()
