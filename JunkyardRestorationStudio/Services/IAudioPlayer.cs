using System.Threading.Tasks;

namespace JunkyardRestorationStudio.Services;

public interface IAudioPlayer
{
    Task PlayAsync(string fileName);

    Task PlaySegmentAsync(string fileName, double startSeconds, double endSeconds);

    void Stop();

    bool IsPlaying { get; }
}