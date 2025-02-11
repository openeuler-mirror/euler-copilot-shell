# Smart Shell

This project is a terminal user interface (TUI) application built using Urwid. It allows users to input commands, which are then validated and executed. If a command cannot be executed, the application interacts with a third-party big model to generate suggestions or corrections.

## Features

- User-friendly command input and output display.
- Command validation and execution.
- Integration with a big model for command suggestions.
- Compatible with pure TTY environments.

## Project Structure

```text
smart-shell/
├── README.md                     # Project documentation
├── requirements.txt              # Project dependencies
└── src
    ├── app
    │   ├── __init__.py
    │   ├── settings.py
    │   └── tui.py                # TUI layout and widget definitions
    ├── backend
    │   ├── __init__.py
    │   └── openai.py             # Logic for interacting with the OpenAI API
    ├── config
    │   ├── __init__.py
    │   ├── manager.py
    │   └── model.py
    ├── main.py                   # Entry point of the TUI application
    └── tool
        ├── __init__.py
        └── command_processor.py  # Command validation and execution logic
```

## Setup Instructions

1. Clone the repository:

   ```sh
   git clone <repository-url>
   cd smart-shell
   ```

2. Install the required dependencies:

   ```sh
   pip install -r requirements.txt
   ```

## Usage

To run the application, execute the following command in your terminal:

```sh
python src/main.py
```

Once the application is running, you can enter commands directly into the input field. If a command is invalid or cannot be executed, the application will provide suggestions based on your input.

## LLM Service Integration

The application utilizes a third-party LLM to enhance user experience by providing command suggestions. The integration is handled in the `backend/openai.py` file, which communicates with the OpenAI-compatible API to retrieve suggestions based on user input.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MulanPSL-2.0 License. See the LICENSE file for more details.
