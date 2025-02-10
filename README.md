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
├── src
│   ├── main.py            # Entry point of the TUI application
│   ├── tui.py             # TUI layout and widget definitions
│   ├── command_processor.py # Command validation and execution logic
│   └── big_model.py       # Logic for interacting with the big model API
├── requirements.txt       # Project dependencies
└── README.md              # Project documentation
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

## Big Model Integration

The application utilizes a third-party big model to enhance user experience by providing command suggestions. The integration is handled in the `big_model.py` file, which communicates with the big model API to retrieve suggestions based on user input.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.
