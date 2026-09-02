using System.Threading.Tasks;

namespace JunkyardRestorationStudio.Services;

public interface IAudioPlayer
{
    Task PlayAsync(string fileName);

    void Stop();

    bool IsPlaying { get; }
}