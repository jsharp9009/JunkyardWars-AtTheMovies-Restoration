import whisper
from whisper.utils import get_writer

audio_path = "C:/EpisodeProcessor/stitched_selected.wav"

print("Loading Model")
model = whisper.load_model("turbo")
print("Transcribing");
result = model.transcribe(audio_path, verbose=False)

output_directory = "./"

print("Writing SRT")
# 3. Export to SRT format
srt_writer = get_writer("srt", output_directory)
srt_writer(result, audio_path)
print("Writing VVT");
# 4. Export to VTT format
json_writer = get_writer("json", output_directory)
json_writer(result, audio_path)

print("SRT and JSON subtitle files generated successfully!")