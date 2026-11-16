#!/usr/bin/env python3
"""Yorumlu komik montaj.

Kullanim:
    python3 montaj.py GIRIS_VIDEO.mp4 CIKIS.mp4

Videoyu dikey 1080x1920 formatina getirir. Belirlenen saniyelerde videoyu
dondurur, yorum ekran goruntusunu ekrana koyar ve yorumu robotik sesle okutur.
Her yorumdan sonra 2-3 saniyelik komik bir ara klip ekler, sonra videoya devam eder.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

BURASI = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = 1080, 1920, 30, 44100
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Yorumlar: ekran goruntusu, okunacak metin, videonun yuzde kacinda cikacagi
YORUMLAR = [
    ("yorumlar/1.jpg", "Zoktay çeyrek porsiyon", 0.15),
    ("yorumlar/2.jpg", "abla mimiklerin", 0.38),
    ("yorumlar/3.jpg", "Hareketlere bakkk", 0.60),
    ("yorumlar/4.jpg", "Niye triplere giriyosun", 0.82),
]
# Her yorumdan sonra gelecek ara klip turu (sirayla)
ARA_KLIPLER = ["zoom_boom", "titreme", "tekrar", "soru"]

VCODEC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]
ACODEC = ["-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2"]
NORMAL = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"setsar=1,fps={FPS}")


def calistir(args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def sure(yol):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", yol], capture_output=True, text=True, check=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def ses_var_mi(yol):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                          "-show_entries", "stream=index", "-of", "csv=p=0", yol],
                         capture_output=True, text=True)
    return bool(out.stdout.strip())


def normallestir(giris, cikis):
    """Videoyu 1080x1920, 30fps, stereo sese cevirir (sesi yoksa sessiz ekler)."""
    if ses_var_mi(giris):
        calistir(["-i", giris, "-vf", NORMAL, *VCODEC, *ACODEC, cikis])
    else:
        calistir(["-i", giris, "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo",
                  "-vf", NORMAL, "-shortest", *VCODEC, *ACODEC, cikis])


def parca(kaynak, bas, son, cikis):
    calistir(["-ss", f"{bas:.3f}", "-to", f"{son:.3f}", "-i", kaynak, *VCODEC, *ACODEC, cikis])


def kare_al(kaynak, t, cikis):
    calistir(["-ss", f"{t:.3f}", "-i", kaynak, "-frames:v", "1", cikis])


def robot_ses(metin, cikis):
    ham = cikis + ".ham.wav"
    subprocess.run(["espeak-ng", "-v", "tr", "-s", "135", "-p", "25", "-w", ham, metin], check=True)
    # Biraz daha robotik: hafif metalik yanki + ses yukseltme
    calistir(["-i", ham, "-af", "aecho=0.8:0.7:12:0.35,volume=2.2,alimiter=limit=0.95",
              "-ar", str(SR), "-ac", "2", cikis])
    os.remove(ham)


def yorum_sahnesi(kare, yorum_img, ses, cikis):
    """Donmus kare + yorum karti + robot ses."""
    d = sure(ses) + 0.7
    kart_w = 960
    fc = (
        f"[0:v]scale={W}:{H},eq=brightness=-0.08,boxblur=2:1,setsar=1[bg];"
        f"[1:v]scale={kart_w}:-1,pad=iw+16:ih+16:8:8:color=white@0.9[kart];"
        f"[bg][kart]overlay=x=(W-w)/2:y=H*0.30:enable='gte(t,0)',"
        f"fade=t=in:st=0:d=0.15,format=yuv420p[v];"
        f"[2:a]adelay=250|250,apad[a]"
    )
    calistir(["-loop", "1", "-t", f"{d:.3f}", "-i", kare, "-i", yorum_img, "-i", ses,
              "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{d:.3f}",
              *VCODEC, *ACODEC, cikis])


def boom_sesi(cikis, d=1.6):
    expr = "0.95*sin(2*PI*(45+90*exp(-9*t))*t)*exp(-2.6*t)+0.25*(random(0)-0.5)*exp(-40*t)"
    calistir(["-f", "lavfi", "-i", f"aevalsrc='{expr}':s={SR}:d={d}",
              "-af", "volume=3,alimiter=limit=0.95", "-ac", "2", cikis])


def ara_klip(tur, kaynak, t, kare, gecici, cikis):
    d = 2.4
    if tur == "zoom_boom":
        # Kare donar, kirmizilasir ve ani zoom yapar, ustune bass "boom"
        boom = os.path.join(gecici, "boom.wav")
        boom_sesi(boom, d)
        fc = (f"[0:v]scale={W*2}:{H*2},zoompan=z='min(1+0.06*on,2.4)':d={int(d*FPS)}:"
              f"x='iw/2-(iw/zoom/2)':y='ih/2.6-(ih/zoom/2.6)':s={W}x{H}:fps={FPS},"
              f"colorbalance=rs=0.55:gs=-0.2:bs=-0.2,eq=contrast=1.4:saturation=1.6,"
              f"setsar=1,format=yuv420p[v]")
        calistir(["-loop", "1", "-t", str(d), "-i", kare, "-i", boom, "-filter_complex", fc,
                  "-map", "[v]", "-map", "1:a", "-t", str(d), *VCODEC, *ACODEC, cikis])
    elif tur == "titreme":
        # Ekran sallanir, ustune robotik "ne" ve boom
        ses = os.path.join(gecici, "ne.wav")
        robot_ses("neee", ses)
        boom = os.path.join(gecici, "boom2.wav")
        boom_sesi(boom, d)
        fc = (f"[0:v]scale={int(W*1.15)}:{int(H*1.15)},"
              f"crop={W}:{H}:x='(iw-{W})/2+60*sin(t*47)':y='(ih-{H})/2+60*cos(t*39)',"
              f"eq=contrast=1.3:saturation=0.2,setsar=1,format=yuv420p[v];"
              f"[1:a][2:a]amix=inputs=2:normalize=0,apad[a]")
        calistir(["-loop", "1", "-t", str(d), "-i", kare, "-i", ses, "-i", boom,
                  "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", str(d),
                  *VCODEC, *ACODEC, cikis])
    elif tur == "tekrar":
        # Son 0.4 saniye ileri-geri-ileri-geri (takilma efekti)
        bas = max(0.0, t - 0.4)
        fc = (f"[0:v]trim=start={bas}:end={t},setpts=PTS-STARTPTS,split=2[a1][b1];"
              f"[b1]reverse[r1];[a1][r1]concat=n=2:v=1:a=0,split=3[x][y][z];"
              f"[x][y][z]concat=n=3:v=1:a=0,setsar=1,format=yuv420p[v];"
              f"[0:a]atrim=start={bas}:end={t},asetpts=PTS-STARTPTS,asplit=2[c1][d1];"
              f"[d1]areverse[e1];[c1][e1]concat=n=2:v=0:a=1,asplit=3[p][q][r];"
              f"[p][q][r]concat=n=3:v=0:a=1[a]")
        calistir(["-i", kaynak, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                  *VCODEC, *ACODEC, cikis])
    elif tur == "soru":
        # Kararan ekran, titreyen dev "?????" yazisi, robot "bruh"
        ses = os.path.join(gecici, "bruh.wav")
        robot_ses("bruh", ses)
        fc = (f"[0:v]scale={W}:{H},eq=brightness=-0.35:saturation=0,boxblur=6:2,"
              f"drawtext=fontfile={FONT}:text='?????':fontsize=230:fontcolor=white:"
              f"borderw=12:bordercolor=black:x=(w-tw)/2+18*sin(t*40):y=(h-th)/2+18*cos(t*33),"
              f"setsar=1,format=yuv420p[v];[1:a]adelay=200|200,apad[a]")
        calistir(["-loop", "1", "-t", str(d), "-i", kare, "-i", ses, "-filter_complex", fc,
                  "-map", "[v]", "-map", "[a]", "-t", str(d), *VCODEC, *ACODEC, cikis])


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    giris, cikis = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    gecici = tempfile.mkdtemp(prefix="montaj_")
    try:
        norm = os.path.join(gecici, "norm.mp4")
        normallestir(giris, norm)
        toplam = sure(norm)
        parcalar, onceki = [], 0.0
        for i, (img, metin, oran) in enumerate(YORUMLAR):
            t = round(toplam * oran, 3)
            p = os.path.join(gecici, f"{i}_a_video.mp4")
            parca(norm, onceki, t, p)
            parcalar.append(p)
            kare = os.path.join(gecici, f"{i}_kare.png")
            kare_al(norm, max(0, t - 0.05), kare)
            ses = os.path.join(gecici, f"{i}_ses.wav")
            robot_ses(metin, ses)
            y = os.path.join(gecici, f"{i}_b_yorum.mp4")
            yorum_sahnesi(kare, os.path.join(BURASI, img), ses, y)
            parcalar.append(y)
            a = os.path.join(gecici, f"{i}_c_ara.mp4")
            ara_klip(ARA_KLIPLER[i % len(ARA_KLIPLER)], norm, t, kare, gecici, a)
            parcalar.append(a)
            onceki = t
        son = os.path.join(gecici, "z_son.mp4")
        parca(norm, onceki, toplam, son)
        parcalar.append(son)
        liste = os.path.join(gecici, "liste.txt")
        with open(liste, "w") as f:
            f.writelines(f"file '{p}'\n" for p in parcalar)
        calistir(["-f", "concat", "-safe", "0", "-i", liste, *VCODEC, *ACODEC,
                  "-movflags", "+faststart", cikis])
        print(f"Bitti: {cikis} ({sure(cikis):.1f} sn)")
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


if __name__ == "__main__":
    main()
