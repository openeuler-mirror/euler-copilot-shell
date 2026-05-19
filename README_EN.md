# Witty Assistant

Witty Assistant is a command-line client of openEuler Intelligence, providing AI-driven command-line interaction experience. It supports multiple LLM backends, integrates the Model Context Protocol (MCP), and provides a modern TUI.

## Core Features

- **Multi-backend support:** Supports OpenAI API LLMs and openEuler Intelligence backends.
- **Intelligent terminal interface:** Provides a textual-based modern TUI.
- **Streaming response:** Displays AI replies in real time.
- **Deployment assistant:** Supports built-in automatic deployment of openEuler Intelligence.
- **One-click authentication:** Provides a browser login process to automatically obtain and save the API keys.

## Installation Description

### Method 1: Installing from the Source Code (Recommended for Developers)

1. Clone a repository.

   ```sh
   git clone https://gitee.com/openeuler/euler-copilot-shell.git -b dev
   cd euler-copilot-shell
   ```

2. Install the dependencies (preferably in a Python virtual environment).

  ```sh
  uv venv --python 3.11 .venv
  source .venv/bin/activate
  uv pip install -e '.[dev]'
  ```

### Method 2: Using the RPM Package

Note: *This method applies only to openEuler 24.03 LTS SP2*.

```sh
sudo dnf install openeuler-intelligence-cli
```

After the installation is complete, you can run the `witty` command to start the application.

## How to Use

Install the RPM package.

```sh
witty
```

View the latest logs.

```sh
witty --logs
```

Set and verify the log level.

```sh
witty --log-level INFO
```

Initialize the openEuler Intelligence backend (only the openEuler OS is supported).

```sh
witty --init
```

Select and set the default agent (applicable only to the openEuler Intelligence backend).

```sh
witty --agent
```

Log in using a browser and automatically save the API key (which requires the configured openEuler Intelligence backend).

```sh
witty --login
```

Before running the command, ensure that the operating environment has a GUI and the default browser can be started. If no GUI is available, you can use X11 forwarding or run the command directly on the target server.

After the application is started, you can directly enter the command in the input box. If the command is invalid or cannot be executed, the application will provide intelligent suggestions based on your input.

### Shortcut Keys for GUI Operations

- Press **Ctrl+S** to open the setting page.
- Press **Ctrl+R** to reset the dialog history.
- Press **Ctrl+T** to select an agent.
- Press **Tab** to switch the focus between the command input box and the output area.
- Press **Esc** to exit the application.

### MCP Tool Interaction

When an MCP-compatible backend is used, the application will perform the following actions when tool confirmation or parameter input is required:

1. **Tool execution confirmation:** The tool name, risk level, and reason to execute are displayed. You can choose to confirm or cancel the execution.
2. **Parameter completion:** A parameter input form is dynamically generated. You can fill in the necessary information and submit it.

The application uses the inline interaction mode and does not open modal dialogs, ensuring a smooth user experience.

### `--init` Command

The `--init` command is used to automatically install and configure the openEuler Intelligence backend on the openEuler OS. It performs the following steps:

1. **System check:** Checks whether the current OS is openEuler.
2. **Environment check:** Checks the DNF package manager and administrator permissions.
3. **Package installation:** Installs the `openeuler-intelligence-installer` RPM package using DNF.
4. **Service deployment:** Runs the deployment script to initialize the system.

**Requirements**

- Only the openEuler OS is supported.
- Administrator permissions (sudo) are required.
- Network connection is required to download the RPM package.

**Notes**

1. This command automatically installs system services. Exercise caution when using it in the production environment.
2. To restart or uninstall the openEuler Intelligence backend, run `witty-manager` as the administrator and follow the instructions.
3. The uninstallation function of `witty-manager` will clear all MongoDB and PostgreSQL data on the machine and reset the Nginx service. Exercise caution when performing this operation.

### `--agent` Command

The `--agent` command is used to select and set the default agent in the command line. It provides a TUI to manage agent configurations.

1. **Agent list:** Automatically obtains and displays all available agents.
2. **Visualized selection:** Selects the agent to be set as the default agent through the TUI.
3. **Configuration saving:** Automatically saves the selected agent to the `eulerintelli.default_app` field in the configuration file.
4. **Instant feedback:** Displays a confirmation message after the configuration is complete.

**Requirements**

- The backend must be set to openEuler Intelligence.
- A valid server connection is required to obtain the agent list.
- If the backend is not openEuler Intelligence, an error message is displayed and a switch is prompted.

**Features**

- The `Intelligent Q&A` option (without agents) is included as the default choice.
- Operations can be canceled without changing the existing configuration.
- Network errors and exceptions are automatically handled.

### `--llm-config` Command

The `--llm-config` command is used to configure the LLM and embedding model parameters of the deployed openEuler Intelligence backend. It provides a simple TUI to manage system-level configurations.

1. **System configuration management:** Directly modifies the system configuration files `/etc/euler-copilot-framework/config.toml` and `/etc/euler-copilot-rag/data_chain/env`.
2. **LLM configuration:** Configures the endpoint, API key, model name, maximum number of output tokens, and temperature parameters of an LLM.
3. **Embedding configuration:** Configures the endpoint, API key, and model name of an embedding model.
4. **Real-time verification:** Automatically verifies API connectivity and configuration validity.
5. **Service restart:** Automatically restarts related system services (`oi-runtime` and `oi-rag`) after the configuration is saved.

**Requirements**

- This command applies only to deployed openEuler Intelligence.
- Administrator permissions (sudo) are required.
- The system configuration file must exist and the write permission is granted.
- A network connection is required to verify the API configuration.

**Features**

- **Tab-based configuration:** LLM and embedding model configurations are managed on different tabs.
- **Automatic verification:** API connectivity is automatically verified after the configuration is entered.
- **Intelligent detection:** The function call type and embedding model type are automatically detected.
- **Secure saving:** The configuration can be saved only after it passes the verification.
- **Service management:** Related system services are automatically restarted for the configuration to take effect.

**Configuration Items**

- **LLMs**

  - **Endpoint address:** Base URL of the LLM API.
  - **API key:** Authentication key for accessing the LLM service.
  - **Model name:** Name of the model to be used.
  - **Maximum number of output tokens:** Maximum number of tokens that can be output in a single request (8,192 by default).
  - **Temperature parameter:** Controls the randomness of generation (default: 0.7).

- **Embedding models**

  - **Endpoint address:** Base URL of the embedding model API.
  - **API key:** Authentication key for accessing the embedding model service.
  - **Model name:** Name of the embedding model to be used.

**Notes**

1. This command directly modifies the system configuration file. Exercise caution when using it in the production environment.
2. After the configuration is saved, the `oi-runtime` and `oi-rag` services will automatically restart, which may affect running services.
3. If the system configuration file does not exist or the permission is insufficient, the tool displays an error message and exits.
4. You are advised to back up the original configuration file before modifying it.

### `--login` Command

The `--login` command is used to obtain the API key of openEuler Intelligence through the default browser and automatically write the key to the local configuration.

1. **Obtaining the authorization address:** Reads the login redirection link from the configured openEuler Intelligence backend.
2. **Local callback service:** Starts a temporary callback server locally to process the data sent back by the browser.
3. **Opening a browser:** Automatically opens the login page where you can log in to the system as prompted.
4. **Saving credentials:** Automatically writes the returned access token into the configuration file after you have successfully logged in to the system.

**Requirements**

- The openEuler Intelligence URL has been configured using the `--init` command or manually.
- The operating environment has a browser available (for headless servers, use graphics forwarding or perform operations locally).
- During login, a network connection is required to access the openEuler Intelligence backend.

If an error occurs, the command outputs detailed information to help you locate the fault, for example, no browser is detected or the URL is not configured.

## Internationalization

The application supports multiple languages and provides English and Chinese interfaces.

### Supported Languages

- **English (en_US)** (default)
- **Simplified Chinese**

### Language Switching

```sh
# Switch to Chinese.
witty --locale zh_CN

# Switch to English.
witty --locale en_US
```

The language setting is automatically saved and takes effect upon the next startup.

### Auto Language Detection

When the application is started, the display language is determined based on the following priorities:

1. Language setting in the user configuration file
2. System environment variables (such as `LANG` and `LC_ALL`)
3. Default language (English)

If the system language is Chinese, the Chinese UI is automatically used when the application is run for the first time.

### Development Documents

For details about how to add new translations for the application or learn about the implementation details of internationalization, see:

- [Internationalization Quick Start](./docs/development/Internationalization Quick Start.md)
- [Internationalization Development Guide](./docs/development/Internationalization Development Guide.md)

## Configuration

The application supports two types of backend configurations and the configuration files are automatically saved in the `~/.config/eulerintelli/smart-shell.json` file.

### Backend Types

1. **OpenAI-compatible APIs** (including LM Studio, vLLM, and Ollama)
2. **openEuler Intelligence**

### Configuration Example

When you run this application for the first time, you can press **Ctrl+S** to set the following parameters.

**OpenAI-compatible API configurations:**

- Base URL: for example, `http://localhost:1234/v1`
- Model: for example, `qwen/qwen3-30b-a3b`
- API key: for example, `sk-xxxxxx`

**openEuler Intelligence configurations:**

- Base URL: for example, `http://your-server:8002`
- API key: your authentication token

### Agent Management

For the openEuler Intelligence backend, the application supports switching between multiple agents:

1. **Default intelligent Q&A:** general AI assistant
2. **Professional agent:** specialized assistant for specific domains

You can press **Ctrl+T** to switch between different agents during runtime.

#### Default Agent Configuration

The application supports the configuration of agents that are started by default:

- **Default agent configuration:** Determines which agent is activated when the application starts and is persistently saved.
- **Agent switching during runtime:** Temporarily switches agents in the current session without affecting the default configuration.

##### Method 1: Command line (modifying the default configuration)

```sh
witty --agent
```

Select the default agent on the GUI. The selection is automatically saved to the configuration file.

##### Method 2: Manually modifying the source code (not recommended)

Edit the `~/.config/eulerintelli/smart-shell.json` configuration file and change the value of the `eulerintelli.default_app` field.

- Set the field to an empty string `""` or delete the field: Use the intelligent Q&A function (without the capability of invoking tools).
- Set the field to a valid agent ID: Use the specified agent as the default.
- Set the field to an invalid agent ID: When the application is started, it will automatically clear the setting and revert to the intelligent Q&A function.

##### Configuration Details

- **Configuration location:** `eulerintelli.default_app` field in `~/.config/eulerintelli/smart-shell.json`
- **Default behavior:** If this field is not set or is left empty, the intelligent Q&A function (general assistant) will be used by default.
- **Automatic application:** The configured default agent is automatically loaded when the application is started.
- **Automatic clearing:** If the configured agent ID does not exist (for example, due to server data changes), the configuration will be automatically cleared and the system will revert to the intelligent Q&A function.

**Configuration Example**

```json
{
  "backend": "eulerintelli",
  "eulerintelli": {
    "base_url": "http://your-server:8002",
    "api_key": "your-api-key",
    "default_app": "your-preferred-agent-id"
  }
}
```

### Log Configuration

The application provides multi-level logging:

- **DEBUG:** detailed debugging information (default)
- **INFO:** basic information
- **WARNING:** warning information
- **ERROR:** error information only

## Log Function

The application provides complete logging functions:

- **Log location:** `~/.cache/openEuler Intelligence/logs/`
- **Log format:** `smart-shell-YYYYMMDD-HHMMSS.log` (local time zone)
- **Automatic clearing:** Old logs and empty log files generated seven days ago are automatically deleted each time the application is started.
- **Command line:** Run the `python src/main.py --logs` command to view the latest logs.
- **Record content:**
  - Program start and exit
  - API request details (URL, status code, and duration)
  - Exception and error information
  - Module-level operation logs

## System Requirements

### Basic Requirements

- **Python:** 3.11 or later
- **OS**: openEuler 24.03 LTS or later
- **Network:** For accessing the configured LLM API service

### Dependency

Core dependencies:

- **textual:** 5.3.0 - TUI framework
- **rich:** 14.1.0 - Rich text rendering
- **httpx:** 0.28.1 - HTTP client
- **openai:** 1.99.6 - OpenAI API client

Development dependencies:

- **ruff:** *Latest* - Code checker

### Special Function Requirements

**Automatic deployment** (using the `--init` command):

- Only the openEuler OS is supported.
- Administrator permissions (sudo) are required.
- The DNF package manager is required.
- A network connection is required.

## Packaging RPM on openEuler

The following steps demonstrate how to use the built-in script to generate an RPM package on openEuler 24.03 LTS or later.

Prerequisites:

- OS: openEuler 24.03 LTS or later
- Tools: rpmdevtools, Git, and Bash
- Administrator permissions (sudo)

Build steps:

1. Clone the repository and switch to the corresponding branch.

   ```sh
   git clone https://gitee.com/openeuler/euler-copilot-shell.git -b dev
   cd euler-copilot-shell
   ```

2. Add the execute permission to the script.

   ```sh
   chmod +x scripts/build/create_tarball.sh scripts/build/build_rpm.sh
   ```

3. Run the RPM build script.

   ```sh
   ./scripts/build/build_rpm.sh
   ```

   After the script is executed, the corresponding binary package and source package are generated in the `RPMS` and `SRPMS` subdirectories under the temporary build directory, and the specific paths are displayed on the terminal.

## Project Structure

```text
smart-shell/
├── README.md                     # Project description
├── pyproject.toml                # Project configuration and dependencies (managed by uv)
├── requirements.txt              # List of pip-compatible dependencies (generated using uv export)
├── uv.lock                       # Lock file generated by uv
├── LICENSE                       # Open-source license
├── distribution/                 # Release-related files
├── docs/                         # Project document directory
│   └── development/              # Development and design documents
│       └── server-side/          # Server-related documents
├── scripts/                      # Deployment script directory
│   └── build/                    # RPM package build script
│   └── deploy/                   # Automatic deployment script
├── tests/                        # Test file directory
└── src/                          # Source code directory
    ├── main.py                   # Application entry point
    ├── app/                      # TUI application module
    │   ├── tui.py                # Main interface application class
    │   ├── mcp_widgets.py        # MCP interaction component
    │   ├── tui_mcp_handler.py    # MCP event handler
    │   ├── settings.py           # Settings interface
    │   ├── css/
    │   │   └── styles.tcss       # TUI style file
    │   ├── deployment/           # Deployment assistant module
    │   │   ├── agent.py          # Agent deployment management
    │   │   ├── models.py         # Deployment configuration model
    │   │   ├── service.py        # Deployment service logic
    │   │   ├── ui.py             # Deployment UI component
    │   │   └── components/       # Deployment component module
    │   └── dialogs/              # Dialog component
    │       ├── agent.py          # Agent selection dialog box
    │       └── common.py         # Common dialog component
    ├── backend/                  # Backend adaptation module
    │   ├── base.py               # Backend client base class
    │   ├── factory.py            # Backend factory class
    │   ├── mcp_handler.py        # MCP event processing interface
    │   ├── openai.py             # OpenAI-compatible client
    │   └── hermes/               # openEuler Intelligence client
    │       ├── client.py         # Hermes API client
    │       ├── constants.py      # Constant definition
    │       ├── exceptions.py     # Exception class definition
    │       ├── mcp_helpers.py    # MCP event helper tool
    │       ├── models.py         # Data model
    │       ├── stream.py         # Streaming response processing
    │       └── services/         # Service-layer component
    ├── config/                   # Configuration management module
    │   ├── manager.py            # Configuration manager
    │   └── model.py              # Configuration data model
    ├── log/                      # Log management module
    │   └── manager.py            # Log manager
    └── tool/                     # Tool module
        ├── command_processor.py  # Command processor
        ├── oi_backend_init.py    # Backend initialization tool
        ├── oi_llm_config.py      # LLM configuration management tool
        ├── oi_select_agent.py    # Agent selection tool
        └── validators.py         # Configuration validator
```

## Contribution

We welcome you to contribute code. You can submit a pull request (PR) or start an issue to discuss any feature enhancements or bug fixes.

## Related Documents

### Developer Documents

- [Overall Project Design](docs/development/Overall Project Design.md) – System architecture and overall design solution
- [TUI Application Module Design](docs/development/TUI Application Module Design.md) – User interface module design
- [Backend Adaptation Module Design](docs/development/Backend Adaptation Module Design.md) – Multi-backend support architecture
- [Deployment Assistant Module Design](docs/development/Deployment Assistant Module Design.md) – Automatic deployment function design
- [Configuration Management Module Design](docs/development/Configuration Management Module Design.md) – Configuration management system design
- [Log Management Module Design](docs/development/Log Management Module Design.md) – Logging system design

### Deployment Documents

- [Installation and Deployment Guide](scripts/deploy/Installation and Deployment Guide.md) – Detailed deployment guide

## Open-Source Licenses

This project is licensed under MulanPSL-2.0. For details, see the [LICENSE](LICENSE) file.
