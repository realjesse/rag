namespace Backend.Indexing;

/// <summary>Splits text into fixed-size, optionally overlapping character chunks.</summary>
public sealed class TextChunker
{
    private readonly int _chunkSize;
    private readonly int _overlap;

    public TextChunker(int chunkSize, int overlap = 0)
    {
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(chunkSize);
        ArgumentOutOfRangeException.ThrowIfNegative(overlap);

        if (overlap >= chunkSize)
        {
            throw new ArgumentOutOfRangeException(nameof(overlap), "Overlap must be smaller than the chunk size.");
        }

        _chunkSize = chunkSize;
        _overlap = overlap;
    }

    /// <summary>
    /// Returns consecutive chunks without changing whitespace or punctuation.
    /// Size and overlap are measured in .NET string characters (UTF-16 code units).
    /// </summary>
    public IReadOnlyList<string> Chunk(string text)
    {
        ArgumentNullException.ThrowIfNull(text);

        var chunks = new List<string>();
        for (var start = 0; start < text.Length; start += _chunkSize - _overlap)
        {
            var length = Math.Min(_chunkSize, text.Length - start);
            chunks.Add(text.Substring(start, length));

            if (start + length == text.Length)
            {
                break;
            }
        }

        return chunks;
    }
}
