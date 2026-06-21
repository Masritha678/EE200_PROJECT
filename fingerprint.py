import os
import glob
import collections
import numpy as np
import librosa
from scipy.ndimage import maximum_filter


SR = 11025 
N_FFT = 2048  
HOP_LENGTH = 512  

PEAK_NEIGHBORHOOD = 20 
PEAK_THRESHOLD_DB = -60  
FAN_VALUE = 15  
MAX_TIME_DELTA = 200  
MIN_TIME_DELTA = 1  



def load_audio(path, sr=SR):
   
    y, _ = librosa.load(
        path,
        sr=sr,
        mono=True,
        duration=60
    )
    return y




def compute_spectrogram(
        y,
        n_fft=N_FFT,
        hop=HOP_LENGTH
):
   
    D = librosa.stft(
        y,
        n_fft=n_fft,
        hop_length=hop,
        window="hann"
    )

    S_db = librosa.amplitude_to_db(
        np.abs(D),
        ref=np.max
    )

    freqs = librosa.fft_frequencies(
        sr=SR,
        n_fft=n_fft
    )

    times = librosa.frames_to_time(
        np.arange(S_db.shape[1]),
        sr=SR,
        hop_length=hop,
        n_fft=n_fft
    )

    return S_db, freqs, times




def get_peaks(
        S_db,
        neighborhood=PEAK_NEIGHBORHOOD,
        thresh=PEAK_THRESHOLD_DB
):
  
    local_max = (
            maximum_filter(
                S_db,
                size=neighborhood
            ) == S_db
    )

    background = S_db < thresh

    detected = local_max & ~background

    freq_bins, time_frames = np.where(
        detected
    )

    order = np.argsort(time_frames)

    return list(
        zip(
            freq_bins[order].tolist(),
            time_frames[order].tolist()
        )
    )




def generate_hashes(
        peaks,
        fan_value=FAN_VALUE,
        min_td=MIN_TIME_DELTA,
        max_td=MAX_TIME_DELTA
):
   
    for i, (f1, t1) in enumerate(peaks):

        for j in range(
                1,
                fan_value + 1
        ):

            if i + j >= len(peaks):
                break

            f2, t2 = peaks[i + j]

            dt = t2 - t1

            if (
                    dt < min_td or
                    dt > max_td
            ):
                continue

            h = f"{f1}|{f2}|{dt}"

            yield h, t1



def fingerprint(y):
   
    S_db, _, _ = compute_spectrogram(y)

    peaks = get_peaks(S_db)

    return list(
        generate_hashes(peaks)
    )



def build_database(song_dir):
   
   
    song_dir = os.path.normpath(song_dir)

    if not os.path.isdir(song_dir):
        raise ValueError(f"Directory not found: {song_dir}")

    db = collections.defaultdict(list)

    songs = []

    
    files = sorted(set(
        glob.glob(
            os.path.join(song_dir, "*.mp3")
        )
        +
        glob.glob(
            os.path.join(song_dir, "*.MP3")
        )
        +
        glob.glob(
            os.path.join(song_dir, "*.wav")
        )
        +
        glob.glob(
            os.path.join(song_dir, "*.WAV")
        )
        +
        glob.glob(
            os.path.join(song_dir, "*.flac")
        )
        +
        glob.glob(
            os.path.join(song_dir, "*.FLAC")
        )
        +
        glob.glob(
            os.path.join(song_dir, "*.ogg")
        )
        +
        glob.glob(
            os.path.join(song_dir, "*.OGG")
        )
    ))

    for idx, path in enumerate(files, 1):

        song_name = os.path.splitext(
            os.path.basename(path)
        )[0]

        songs.append(song_name)

        print(
            f"[{idx}/{len(files)}] Fingerprinting: {song_name}"
        )

        try:
            y = load_audio(path)
            hashes = fingerprint(y)

            for h, t in hashes:
                db[h].append(
                    (
                        song_name,
                        t
                    )
                )
        except Exception as e:
            print(f"  ⚠️ Error processing {song_name}: {e}")
            continue

    return db, songs




def identify(
        query_y,
        db,
        top_n=5
):
   
    query_hashes = fingerprint(
        query_y
    )

    offset_counts = collections.defaultdict(
        lambda: collections.Counter()
    )

    for h, qt in query_hashes:

        if h not in db:
            continue

        for song, dt in db[h]:
            offset = dt - qt

            offset_counts[song][offset] += 1

    scores = {}

    for song, counter in offset_counts.items():
        scores[song] = counter.most_common(
            1
        )[0][1]

    ranked = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return ranked[:top_n]




def get_offset_histogram(
        query_y,
        db,
        target_song
):
    
    query_hashes = fingerprint(
        query_y
    )

    counter = collections.Counter()

    for h, qt in query_hashes:

        if h in db:

            for song, dt in db[h]:

                if song == target_song:
                    counter[
                        dt - qt
                        ] += 1

    return counter
