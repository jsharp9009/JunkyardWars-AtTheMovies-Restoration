using NAudio.Wave;
using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

namespace JunkyardRestorationStudio.Services;

public class AudioPlayer : IAudioPlayer, IDisposable
{
    private WaveOutEvent? outputDevice;
    private AudioFileReader? audioFile;
    private CancellationTokenSource? playbackCancellation;

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

    public async Task PlaySegmentAsync(string fileName, double startSeconds, double endSeconds)
    {
        Stop();

        if (!File.Exists(fileName) || endSeconds <= startSeconds)
            return;

        audioFile = new AudioFileReader(fileName);

        var duration = audioFile.TotalTime.TotalSeconds;
        startSeconds = Math.Clamp(startSeconds, 0, duration);
        endSeconds = Math.Clamp(endSeconds, startSeconds, duration);

        audioFile.CurrentTime = TimeSpan.FromSeconds(startSeconds);
        outputDevice = new WaveOutEvent();
        outputDevice.Init(audioFile);
        outputDevice.Play();

        playbackCancellation = new CancellationTokenSource();
        var token = playbackCancellation.Token;
        var length = TimeSpan.FromSeconds(endSeconds - startSeconds);

        try
        {
            await Task.Delay(length, token);
        }
        catch (OperationCanceledException)
        {
            return;
        }

        if (!token.IsCancellationRequested)
            Stop();
    }

    public void Stop()
    {
        playbackCancellation?.Cancel();
        playbackCancellation?.Dispose();
        playbackCancellation = null;

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