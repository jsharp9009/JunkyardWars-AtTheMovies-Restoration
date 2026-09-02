using NAudio.Wave;
using System;
using System.IO;
using System.Threading.Tasks;

namespace JunkyardRestorationStudio.Services;

public class AudioPlayer : IAudioPlayer, IDisposable
{
    private WaveOutEvent? outputDevice;
    private AudioFileReader? audioFile;

    public bool IsPlaying =>
        outputDevice?.PlaybackState == PlaybackState.Playing;

    public async Task PlayAsync(string fileName)
    {
        Stop();

        if (!File.Exists(fileName))
            return;

        audioFile = new AudioFileReader(fileName);

        outputDevice = new WaveOutEvent();

        outputDevice.Init(audioFile);

        outputDevice.Play();

        await Task.CompletedTask;
    }

    public void Stop()
    {
        outputDevice?.Stop();

        outputDevice?.Dispose();
        outputDevice = null;

        audioFile?.Dispose();
        audioFile = null;
    }

    public void Dispose()
    {
        Stop();
    }
}