# AI Story Rewriter

A production-ready desktop application for batch processing English SRT story files using Google Gemini API to rewrite stories into more engaging, natural, and emotionally compelling narratives.

## Features

- **Batch Processing**: Process hundreds of SRT files sequentially with automatic context isolation
- **AI-Powered Rewriting**: Uses Google Gemini API to enhance storytelling while preserving core plot
- **Quality Control**: Built-in QC system with automatic correction attempts
- **CTR Title Generation**: Generates compelling YouTube-style titles for each story
- **SRT Engine**: Robust parser, writer, and validator for subtitle files
- **Modern UI**: Dark-themed PySide6 interface with real-time progress tracking
- **History Tracking**: Keeps records of all processed files
- **Resume Support**: Resume interrupted batches from where they left off
- **Error Handling**: Comprehensive error handling with retry logic and exponential backoff

## Requirements

- Python 3.11+ (tested with Python 3.13)
- Google Gemini API key

## Installation

1. Clone or download this repository
2. Navigate to the project directory:
   ```bash
   cd ai_story_rewriter
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up your API key:
   - Copy `.env.example` to `.env`
   - Add your Gemini API key:
     ```
     GEMINI_API_KEY=your_api_key_here
     ```

## Usage

1. Run the application:
   ```bash
   python main.py
   ```

2. In the Settings tab:
   - Enter your Gemini API key
   - Select the Gemini model (default: gemini-3.8-flash)
   - Configure processing options (max retry: 3, backoff: 2s → 4s → 8s, timeout: 60s)
   - Click "Save Settings"

3. In the Queue tab:
   - Select input folder containing `.srt` files
   - Select output folder for processed files
   - Click "Scan Files" to load the queue
   - Click "START" to begin processing

4. Monitor progress in the center panel and logs on the right

5. View processing history in the History tab

## Project Structure

```
ai_story_rewriter/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── README.md              # This file
├── app/
│   ├── ui/                # PySide6 UI components
│   │   ├── main_window.py
│   │   ├── widgets.py
│   │   └── styles.py
│   ├── ai/                # AI integration
│   │   ├── gemini_client.py
│   │   ├── prompts.py
│   │   └── ai_service.py
│   ├── srt/               # SRT processing
│   │   ├── parser.py
│   │   ├── writer.py
│   │   └── validator.py
│   ├── pipeline/          # Processing pipeline
│   │   ├── story_processor.py
│   │   └── batch_processor.py
│   ├── storage/           # Settings and history
│   │   ├── settings.py
│   │   └── history.py
│   └── utils/             # Utilities
│       ├── filenames.py
│       ├── logger.py
│       └── text_utils.py
├── input/                 # Default input folder
├── output/                # Default output folder
├── logs/                  # Application logs
└── temp/                  # Temporary files
```

## Processing Pipeline

Each SRT file goes through the following stages:

1. **READ**: Parse SRT file and extract story text
2. **ANALYZE**: AI analyzes story structure (optional)
3. **REWRITE**: AI rewrites story for better engagement
4. **QC**: Quality control check with automatic corrections
5. **TITLE**: Generate CTR title for YouTube
6. **BUILD SRT**: Map rewritten text to original timeline
7. **VALIDATE**: Validate output SRT format
8. **SAVE**: Write final SRT file with generated title
9. **RESET**: Clear context before next file

## Important Notes

- **Sequential Processing**: Each story is processed independently with complete context reset between files
- **No Translation**: The source stories are already in English; this tool rewrites them for better storytelling
- **Context Isolation**: Information from one story never leaks into another
- **Natural Sorting**: Files are sorted numerically (001, 002, 010) not lexicographically
- **Retry Logic**: Failed API calls are retried with exponential backoff
- **Failed Files**: Failed files are saved to a `failed/` subfolder in the output directory

## Configuration

Settings are stored in `settings.json` and include:

- API key
- Model name
- Input/output folders
- Rewrite intensity (light/balanced/deep)
- Max retry count
- Whether to save failed files
- Subtitle formatting limits

## Testing

Run tests with:
```bash
python -m pytest tests/
```

## Troubleshooting

**API Connection Failed**
- Verify your API key is correct
- Check your internet connection
- Ensure you have API quota available

**SRT Parse Error**
- Ensure files are valid SRT format
- Check file encoding (UTF-8 recommended)
- Review logs for specific error details

**Processing Slow**
- Consider using a faster model (gemini-1.5-flash)
- Check your internet connection speed
- Reduce batch size for testing

## License

This project is provided as-is for educational and commercial use.

## Technical Decisions

- **PySide6**: Chosen for modern, cross-platform desktop UI
- **Gemini 1.5**: Latest Google model with strong storytelling capabilities
- **SQLite-like JSON storage**: Simple, file-based settings/history without database complexity
- **QThread**: Background processing to keep UI responsive
- **Sequential Processing**: Ensures context isolation and prevents cross-contamination between stories

## Future Enhancements

- TTS integration for audio generation
- More advanced QC metrics
- Custom prompt templates
- Batch resume from checkpoint
- Multi-language support
- Cloud storage integration
