import whisper
from whisper.utils import get_writer

audio_path = "C:/Users/jshar/Desktop/From Youtube/audio.wav"

print("Loading Model")
model = whisper.load_model("turbo")
print("Transcribing");

result = model.transcribe(
    audio_path,
    language="ru",
    task="transcribe",
    word_timestamps=True,
    condition_on_previous_text=False,
    initial_prompt=(
        "Это телепередача Junkyard Wars об автомобилях, "
        "механике, двигателях, машинах и инженерных соревнованиях. "
        "Используются технические термины и названия деталей автомобилей."
    ),
    verbose=False,
)

output_directory = "./"

print("Writing SRT")
# 3. Export to SRT format
srt_writer = get_writer("srt", output_directory)
srt_writer(result, audio_path)
print("Writing JSON");
# 4. Export to VTT format
json_writer = get_writer("json", output_directory)
json_writer(result, audio_path)

print("SRT and JSON subtitle files generated successfully!")