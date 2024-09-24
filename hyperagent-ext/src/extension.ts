import * as vscode from 'vscode';
import * as WebSocket from 'ws';

interface DataItem {
	text: string;
  }
  

interface DisplayDataMessage {
type: string;
value: {
	id: string;
	items: DataItem[];
};
}

export function activate(context: vscode.ExtensionContext) {
	// Get the API session token from the extension's configuration

	const config = vscode.workspace.getConfiguration('chatgpt');

	// Create a new ChatGPTViewProvider instance and register it with the extension's context
	const provider = new ChatGPTViewProvider(context.extensionUri);
	

	// Put configuration settings into the provider
	provider.selectedInsideCodeblock = config.get('selectedInsideCodeblock') || false;
	provider.pasteOnClick = config.get('pasteOnClick') || false;
	provider.keepConversation = config.get('keepConversation') || false;
	provider.timeoutLength = config.get('timeoutLength') || 60;

	context.subscriptions.push(
		vscode.window.registerWebviewViewProvider(ChatGPTViewProvider.viewType, provider,  {
			webviewOptions: { retainContextWhenHidden: true }
		})
	);


	// Register the commands that can be called from the extension's package.json
	const commandHandler = (command:string) => {
		const config = vscode.workspace.getConfiguration('chatgpt');
		const prompt = config.get(command) as string;
		provider.search(prompt);
	};


	const commandAsk = vscode.commands.registerCommand('chatgpt.ask', () => {
		vscode.window.showInputBox({ prompt: 'What do you want to do?' }).then((value) => {
			provider.search(value);
		});
	});

	const commandExplain = vscode.commands.registerCommand('chatgpt.explain', () => {	
		commandHandler('promptPrefix.explain');
	});
	const commandRefactor = vscode.commands.registerCommand('chatgpt.refactor', () => {
		commandHandler('promptPrefix.refactor');
	});
	const commandOptimize = vscode.commands.registerCommand('chatgpt.optimize', () => {
		commandHandler('promptPrefix.optimize');
	});
	const commandProblems = vscode.commands.registerCommand('chatgpt.findProblems', () => {
		commandHandler('promptPrefix.findProblems');
	});


	context.subscriptions.push(commandAsk, commandExplain, commandRefactor, commandOptimize, commandProblems);



	// Change the extension's session token when configuration is changed
	vscode.workspace.onDidChangeConfiguration((event: vscode.ConfigurationChangeEvent) => {
		if (event.affectsConfiguration('chatgpt.sessionToken')) {
			// Get the extension's configuration
			const config = vscode.workspace.getConfiguration('chatgpt');
			const sessionToken = config.get('sessionToken') as string|undefined;
			// add the new token to the provider

		} else if (event.affectsConfiguration('chatgpt.selectedInsideCodeblock')) {
			const config = vscode.workspace.getConfiguration('chatgpt');
			provider.selectedInsideCodeblock = config.get('selectedInsideCodeblock') || false;

		} else if (event.affectsConfiguration('chatgpt.pasteOnClick')) {
			const config = vscode.workspace.getConfiguration('chatgpt');
			provider.pasteOnClick = config.get('pasteOnClick') || false;

		} else if (event.affectsConfiguration('chatgpt.keepConversation')) {
			const config = vscode.workspace.getConfiguration('chatgpt');
			provider.keepConversation = config.get('keepConversation') || false;

		}else if (event.affectsConfiguration('chatgpt.timeoutLength')) {
			const config = vscode.workspace.getConfiguration('chatgpt');
			provider.timeoutLength = config.get('timeoutLength') || 60;
		}
});
}



class ChatGPTViewProvider implements vscode.WebviewViewProvider {
	public static readonly viewType = 'chatgpt.chatView';

	private _view?: vscode.WebviewView;

	// This variable holds a reference to the ChatGPTAPI instance
	private _ws: WebSocket | null = null
	private _chatHistory: { agent: string, message: string }[] = [];
	private _internalHistoryNav: {agent: string, message: string, summary: string}[] = [];
	private _internalHistoryEdit: {agent: string, message: string, summary: string}[] = [];
	private _sessionStarted = false;
	private _latestMessage: string | null = null;

	private _response?: string;
	private _prompt?: string;
	private _fullPrompt?: string;


	public selectedInsideCodeblock = false;
	public pasteOnClick = true;
	public keepConversation = true;
	public timeoutLength = 60;
	private _sessionToken?: string;
	
	public async connectWebSocket() {
		if (!this._ws || this._ws.readyState === WebSocket.CLOSED) {
			this._ws = new WebSocket('ws://localhost:8999/ws');

			this._ws.on('open', () => {
				console.log('WebSocket connection established');
				this.initializeSession();
			});

			this._ws.on('error', (error) => {
				console.error('WebSocket error:', error);
			});

			// Register the WebSocket message event handler
			this._ws.on('message', (data: WebSocket.Data) => {
				this.handleIncomingMessage(data);
			});

			// Wait for the connection to be established
			await new Promise((resolve) => {
				if (this._ws!.readyState === WebSocket.OPEN) {
					resolve(null);
				} else {
					this._ws!.on('open', resolve);
				}
			});
		}
	}

	  private async initializeSession() {
        if (this._ws && this._ws.readyState === WebSocket.OPEN && !this._sessionStarted) {
            const startMessage = {
                action: "start_agent",
                agent_name: "TestAgent",
                message: "Hello"
            };
            this._ws.send(JSON.stringify(startMessage));
            this._sessionStarted = true;
        }
    }
	// In the constructor, we store the URI of the extension
	constructor(private readonly _extensionUri: vscode.Uri) {
		this.connectWebSocket();
	}


	public resolveWebviewView(
		webviewView: vscode.WebviewView,
		context: vscode.WebviewViewResolveContext,
		_token: vscode.CancellationToken,
	) {
		this._view = webviewView;

		// set options for the webview
		webviewView.webview.options = {
			// Allow scripts in the webview
			enableScripts: true,
			localResourceRoots: [
				this._extensionUri
			]
		};

		// set the HTML for the webview
		webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

		// add an event listener for messages received by the webview
		webviewView.webview.onDidReceiveMessage(data => {
			switch (data.type) {
				case 'codeSelected':
					{
						// do nothing if the pasteOnClick option is disabled
						if (!this.pasteOnClick) {
							break;
						}

						let code = data.value;
						code = code.replace(/([^\\])(\$)([^{0-9])/g, "$1\\$$$3");

						// insert the code as a snippet into the active text editor
						vscode.window.activeTextEditor?.insertSnippet(new vscode.SnippetString(code));
						break;
					}
				case 'prompt':
					{
						this.search(data.value);
					}
			}
		});
	}

	// Method to handle incoming messages
	private handleIncomingMessage(data: WebSocket.Data): void {
		const parsedData = JSON.parse(data.toString());
		if (parsedData.message && parsedData.message.content) {
			const response = parsedData.message.content;
			const agent = parsedData.sender
			const is_internal = parsedData.internal
			const _summary = parsedData.summary
			const is_waiting = (agent != "simple"); 
			if (!is_internal)
				this._chatHistory.push({ agent: 'RepoPilot', message: response});
			else if (agent == "navigator") {
				this._internalHistoryNav.push({agent: agent, message: response, summary: _summary})
			}
			else if (agent == "editor") {
				this._internalHistoryEdit.push({agent: agent, message: response, summary: _summary})
			}
			this._latestMessage = response;

			if (this._view && this._view.visible) {
				if (!is_waiting)
					this._view.webview.postMessage({ type: 'updateChatHistory', value: this._chatHistory });
				else {
					this._view.webview.postMessage({ type: 'updateChatHistoryW', value: this._chatHistory });
				}
				this._view.webview.postMessage({ type: 'updateInternalHistoryNav', value: this._internalHistoryNav});
				this._view.webview.postMessage({ type: 'updateInternalHistoryEdit', value: this._internalHistoryEdit})
			}
		}
	}


	public async search(prompt?:string) {
		if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket is not connected.');
            return;
        }

		this._prompt = prompt;
		if (!prompt) {
			prompt = '';
		};

		// focus gpt activity from activity bar
		if (!this._view) {
			await vscode.commands.executeCommand('chatgpt.chatView.focus');
		} else {
			this._view?.show?.(true);
		}
		
		let response = '';

		// Get the selected text of the active editor
		const selection = vscode.window.activeTextEditor?.selection;
		// const selectedText = vscode.window.activeTextEditor?.document.getText(selection);
		const selectedText = '';
		let searchPrompt = '';

		if (selection && selectedText) {
			// If there is a selection, add the prompt and the selected text to the search prompt
			if (this.selectedInsideCodeblock) {
				searchPrompt = `${prompt}\n\`\`\`\n${selectedText}\n\`\`\``;
			} else {
				searchPrompt = `${prompt}\n${selectedText}\n`;
			}
		} else {
			// Otherwise, just use the prompt if user typed it
			searchPrompt = prompt;
		}

		this._fullPrompt = searchPrompt;


		try {
	  
			if (!this._ws) {
			  throw new Error('WebSocket connection not established');
			}
			// Send the search prompt
			const message = {
			  action: 'send_message',
			  message: searchPrompt
			};


			this._chatHistory.push({ agent: 'User', message: searchPrompt });
			if (this._view && this._view.visible) {
			  this._view.webview.postMessage({ type: 'updateChatHistory', value: this._chatHistory });
			}

			this._ws.send(JSON.stringify(message));
			  this.logChatHistory()
		
			} catch (e) {
				console.log("lol")
				console.error(e);
				response = `[ERROR] ${e}`;
				this._chatHistory.push({ agent: 'Error', message: response });
				if (this._view && this._view.visible) {
				  this._view.webview.postMessage({ type: 'updateChatHistory', value: this._chatHistory });
				}
			  }

	}
	public logChatHistory(): void {
        console.log('Chat History:');
        this._chatHistory.forEach((message, index) => {
            console.log(`Message ${index + 1}:`);
            console.log(`Agent: ${message.agent}`);
            console.log(`Message: ${message.message}`);
            console.log('----------------------');
        });
    }

	public getData(contentId: string): DataItem[] {
		// Dummy data for demonstration; replace with your actual data fetching logic
		const dummyData: Record<string, DataItem[]> = {
		  navigator: [{ text: 'Navigator Item 1' }, { text: 'Navigator Item 2' }],
		  executor: [{ text: 'Executor Item 1' }, { text: 'Executor Item 2' }],
		  editor: [{ text: 'Editor Item 1' }, { text: 'Editor Item 2' }],
		  terminal: [{ text: 'Terminal Item 1' }, { text: 'Terminal Item 2' }],
		};
		return dummyData[contentId] || [];
	  }

	private _getHtmlForWebview(webview: vscode.Webview) {
		const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'main.js'));

		const microlightUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'scripts', 'microlight.min.js'));
		const tailwindUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'scripts', 'tailwind.min.js'));
		const showdownUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'scripts', 'showdown.min.js'));
		const vendorMarkedJs = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'scripts', 'marked.min.js'));
		const vendorHighlightCss = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'scripts', 'highlight.min.css'));
		const vendorHighlightJs = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'scripts', 'highlight.min.js'));
		const font = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'scripts', 'jsr.woff2'));

		return `<!DOCTYPE html>
		  <html lang="en">
		  <head>
			<meta charset="UTF-8">
			<meta name="viewport" content="width=device-width, initial-scale=1.0">

			<link href="${vendorHighlightCss}" rel="stylesheet">
			<script src="${tailwindUri}"></script>
			<script src="${showdownUri}"></script>
			<script src="${microlightUri}"></script>
			<script src="${vendorMarkedJs}"></script>
			<script src="${vendorHighlightJs}"></script>
			<style>
			  @font-face {
				font-family: 'Just Sans Medium';
				src: url('${font}') format('woff2');
				font-weight: normal;
				font-style: normal;
				}
			
				body {
				font-family: 'Just Sans Medium', var(--vscode-editor-font-family, Consolas, 'Courier New', monospace);
				font-size: 11.5px;
				color: var(--vscode-editor-foreground, #ffffff);
				background-color: var(--vscode-editor-background, #1e1e1e);
				display: flex;
				flex-direction: column;
				height: 100vh;
				margin: 0;
				}
			  .header {
				background-color: #2d2d2d;
				padding: 10px;
				text-align: center;
				font-size: 1.5em;
				border-bottom: 1px solid #444;
			  }
			  .chat-container {
				flex: 1;
				display: flex;
				flex-direction: column;
				padding: 10px;
				overflow-y: auto;
			  }
			  .chat-message {
				margin-bottom: 10px;
				padding: 10px;
				border-radius: 5px;
				background-color: #2d2d2d;
				word-wrap: break-word;
				white-space: pre-wrap;
			  }
			  .chat-message strong {
				display: block;
				margin-bottom: 5px;
			  }
			  .chat-message + .chat-message {
				border-top: 1px solid #444;
				padding-top: 10px;
			  }
			  .input-container {
				display: flex;
				padding: 10px;
				background-color: #2d2d2d;
				border-top: 1px solid #444;
			  }
			  .input-container input {
				flex: 1;
				padding: 10px;
				border: none;
				border-radius: 5px;
				background-color: #3d3d3d;
				color: #ffffff;
			  }
			  .input-container input:focus {
				outline: none;
				background-color: #4d4d4d;
			  }
			  .execution-trace-btn {
				background-color: var(--vscode-button-background);
				color: var(--vscode-button-foreground);
				border: none;
				padding: 10px;
				border-radius: 5px;
				cursor: pointer;
				margin-left: 10px;
			  }
			  .execution-trace-btn:hover {
				background-color: var(--vscode-button-hoverBackground);
			  }
			  .modal {
				display: none;
				position: fixed;
				z-index: 1;
				left: 0;
				top: 0;
				width: 100%;
				height: 100%;
				overflow: auto;
				background-color: rgba(0,0,0,0.4);
			  }
			  .modal-content {
				background-color: var(--vscode-editor-background);
				margin: 5% auto;
				padding: 20px;
				border: 1px solid var(--vscode-panel-border);
				width: 80%;
				color: var(--vscode-editor-foreground);
				border-radius: 10px;
			  }
			  .modal-header {
				font-size: 1.5em;
				color: var(--vscode-editor-foreground);
				margin-bottom: 10px;
			  }
			  .modal-section {
				margin-bottom: 20px;
			  }
			  .modal-section-header {
				font-size: 1.2em;
				color: var(--vscode-editor-foreground);
				margin-bottom: 10px;
			  }
			  .modal-section-content {
				background-color: #2d2d2d;
				padding: 10px;
				border-radius: 5px;
				cursor: pointer;
			  }
			  .modal-section-content:hover {
				background-color: #3d3d3d;
			  }
			  .close {
				color: var(--vscode-editor-foreground);
				float: right;
				font-size: 28px;
				font-weight: bold;
				cursor: pointer;
			  }
			  .close:hover,
			  .close:focus {
				color: var(--vscode-textLink-activeForeground);
				text-decoration: none;
				cursor: pointer;
			  }
			</style>
		  </head>
		  <body>
			<div id="chat-history" class="chat-container"></div>
			<div class="input-container">
			  <input type="text" id="prompt-input" placeholder="Type your message here..." />
			  <button id="execution-trace-btn" class="execution-trace-btn">Execution Trace</button>
			</div>
			<div id="execution-trace-modal" class="modal">
			  <div class="modal-content">
				<span class="close">&times;</span>
				<div class="modal-header">Task Status</div>
				<div class="modal-section">
				  <div class="modal-section-header">Running Agents</div>
				  <div class="modal-section-content" id="navigator">Navigator</div>
				  <div class="modal-section-content" id="executor">Executor</div>
				  <div class="modal-section-content" id="editor">Editor</div>
				</div>
				<div class="modal-section">
				  <div class="modal-section-header">Terminal Section</div>
				  <div class="modal-section-content" id="terminal">Terminal</div>
				</div>
			  </div>
			</div>
			<!-- Nested Modals -->
			<div id="navigator-modal" class="modal">
			<div class="modal-content">
				<span class="close">&times;</span>
				<div class="modal-header">Navigator</div>
				<div class="modal-section-content" id="navigator-content"></div>
			</div>
			</div>

			<div id="executor-modal" class="modal">
			<div class="modal-content">
				<span class="close">&times;</span>
				<div class="modal-header">Executor</div>
				<div class="modal-section-content" id="executor-content"></div>
			</div>
			</div>

			<div id="editor-modal" class="modal">
			<div class="modal-content">
				<span class="close">&times;</span>
				<div class="modal-header">Editor</div>
				<div class="modal-section-content" id="editor-content"></div>
			</div>
			</div>

			<div id="terminal-modal" class="modal">
			<div class="modal-content">
				<span class="close">&times;</span>
				<div class="modal-header">Terminal</div>
				<div class="modal-section-content" id="terminal-content"></div>
			</div>
			</div>
			<script src="${scriptUri}"></script>
		  </body>
		  </html>`;
	  }
	  
	  
	  
	}	  

// This method is called when your extension is deactivated
export function deactivate() {}