// @ts-ignore 

// This script will be run within the webview itself
// It cannot access the main VS Code APIs directly.

(function () {
  const vscode = acquireVsCodeApi();

  marked.setOptions({
        renderer: new marked.Renderer(),
        highlight: function (code, _lang) {
            return hljs.highlightAuto(code).value;
        },
        langPrefix: 'hljs language-',
        pedantic: false,
        gfm: true,
        breaks: true,
        sanitize: false,
        smartypants: false,
        xhtml: false
    });

  // Function to fetch and display data in nested modals
  function displaySubModal(modalId, headerText, contentId) {
      const subModal = document.getElementById(modalId);
      const subModalHeader = subModal.querySelector('.modal-header');
      const subModalContent = subModal.querySelector('.modal-section-content');

      // Set header text
      subModalHeader.innerText = headerText;

      // Fetch data from VSCode API or any other source
      vscode.postMessage({ type: 'fetchData', value: contentId });

      // Show the sub-modal
      subModal.style.display = "block";
  }

  window.addEventListener('message', event => {
      const message = event.data;
      switch (message.type) {
          case 'updateChatHistory':
              const chatHistory = message.value;
              const chatHistoryDiv = document.getElementById('chat-history');
              chatHistoryDiv.innerHTML = '';
              chatHistory.forEach(chat => {
                  const chatBlock = document.createElement('div');
                  chatBlock.className = `chat-message ${chat.agent === 'User' ? 'user' : 'RepoPilot'}`;
                //   chatBlock.innerHTML = `<strong>${chat.agent}:</strong> <pre style="white-space: pre-wrap; word-wrap: break-word;">${chat.message}</pre>`;
                chatBlock.innerHTML = `<strong style="font-family: 'Just Sans Medium', Consolas, 'Courier New', monospace; font-size: 13.2px;">${chat.agent}:</strong> <pre style="font-family: 'Just Sans Medium', Consolas, 'Courier New', monospace; font-size: 12.5px; white-space: pre-wrap; word-wrap: break-word;">${chat.message}</pre>`;
                // chatBlock.innerHTML = `<strong>${chat.agent}:</strong> <pre>${chat.message}</pre>`;
                  chatHistoryDiv.appendChild(chatBlock);
              });
              chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight;
              break;
              
              case 'updateChatHistoryW':
                const chatHistoryW = message.value;
                const chatHistoryDivW = document.getElementById('chat-history');
                chatHistoryDivW.innerHTML = '';
                chatHistoryW.forEach(chat => {
                    const chatBlock = document.createElement('div');
                    chatBlock.className = `chat-message ${chat.agent === 'User' ? 'user' : 'RepoPilot'}`;
                  //   chatBlock.innerHTML = `<strong>${chat.agent}:</strong> <pre style="white-space: pre-wrap; word-wrap: break-word;">${chat.message}</pre>`;
                  chatBlock.innerHTML = `<strong style="font-family: 'Just Sans Medium', Consolas, 'Courier New', monospace; font-size: 13.2px;">${chat.agent}:</strong> <pre style="font-family: 'Just Sans Medium', Consolas, 'Courier New', monospace; font-size: 12.5px; white-space: pre-wrap; word-wrap: break-word;">${chat.message}</pre>`;
                  // chatBlock.innerHTML = `<strong>${chat.agent}:</strong> <pre>${chat.message}</pre>`;
                    chatHistoryDivW.appendChild(chatBlock);
                });
                const spinnerBlock = document.createElement('div');
                spinnerBlock.className = 'spinner-block';
                spinnerBlock.innerHTML = `
                <strong>RepoPilot:</strong>
                <div class="flex items-center">
                    <span>This task seems complex. Waiting for RepoPilot...</span>
                    <div
                    class="inline-block h-4 w-4 ml-2 animate-spin rounded-full border-2 border-solid border-current border-r-transparent align-[-0.125em] text-blue-600 motion-reduce:animate-[spin_1.5s_linear_infinite]"
                    role="status">
                    <span
                        class="!absolute !-m-px !h-px !w-px !overflow-hidden !whitespace-nowrap !border-0 !p-0 ![clip:rect(0,0,0,0)]"
                        >Loading...</span
                    </div>
                </div>`;                  
                chatHistoryDivW.appendChild(spinnerBlock);

                

                chatHistoryDivW.scrollTop = chatHistoryDivW.scrollHeight;
                break;
            case 'updateInternalHistoryNav':
              const data = message.value;
              const targetContent = document.getElementById(`navigator-content`);
              targetContent.innerHTML = ''; 
              data.forEach(item => {
                const details = document.createElement('details')
                details.className = 'bg-gray shadow rounded p-4 mb-4';
                const summary = document.createElement('summary');
                summary.className = 'font-bold cursor-pointer';
                summary.textContent = item.summary;
                const content = document.createElement('div');
                content.className = 'mt-2';
                content.innerHTML = marked.parse(item.message);
                details.appendChild(summary);
                details.appendChild(content);
                targetContent.appendChild(details);
              });
              break;
            // case 'updateInternalHistoryEdit':
            //   const dataedit = message.value;
            //   const targetContentedit = document.getElementById(`editor-content`);
            //   targetContentedit.innerHTML = '';
            //   dataedit.forEach(item => {
            //     const itemDivEdit = document.createElement('div');
            //     itemDivEdit.className = 'modal-section-content';
            //     // itemDivEdit.innerText = marked.parse(item.message); 
            //     itemDivEdit.innerHTML = marked.parse(item.message); 
            //     targetContentedit.appendChild(itemDivEdit);
            //   });
            //   break;
            case 'updateInternalHistoryEdit':
                const dataedit = message.value;
                console.log('dataedit:', dataedit);  // Debugging: Log the dataedit array
                const targetContentedit = document.getElementById('editor-content');
                targetContentedit.innerHTML = '';

                dataedit.forEach(item => {
                const details = document.createElement('details');
                details.className = 'bg-gray shadow rounded p-4 mb-4';

                const summary = document.createElement('summary');
                summary.className = 'font-bold cursor-pointer';
                summary.textContent = item.summary;

                const content = document.createElement('div');
                content.className = 'mt-2';
                content.innerHTML = marked.parse(item.message);
                console.log('marked content:', content.innerHTML);  // Debugging: Log the converted HTML content

                details.appendChild(summary);
                details.appendChild(content);
                targetContentedit.appendChild(details);
                });
                break;
            }
  });

  document.getElementById('prompt-input').addEventListener('keydown', event => {
      if (event.key === 'Enter') {
          const prompt = event.target.value;
          vscode.postMessage({ type: 'prompt', value: prompt });
          event.target.value = '';
      }
  });

  const executionTraceBtn = document.getElementById('execution-trace-btn');
  const modal = document.getElementById('execution-trace-modal');
  const closeBtn = modal.querySelector('.close');

  // Close buttons for nested modals
  const navigatorCloseBtn = document.getElementById('navigator-modal').querySelector('.close');
  const executorCloseBtn = document.getElementById('executor-modal').querySelector('.close');
  const editorCloseBtn = document.getElementById('editor-modal').querySelector('.close');
  const terminalCloseBtn = document.getElementById('terminal-modal').querySelector('.close');

  executionTraceBtn.onclick = function() {
      modal.style.display = "block";
  }

  closeBtn.onclick = function() {
      modal.style.display = "none";
  }

  navigatorCloseBtn.onclick = function() {
      document.getElementById('navigator-modal').style.display = "none";
  }

  executorCloseBtn.onclick = function() {
      document.getElementById('executor-modal').style.display = "none";
  }

  editorCloseBtn.onclick = function() {
      document.getElementById('editor-modal').style.display = "none";
  }

  terminalCloseBtn.onclick = function() {
      document.getElementById('terminal-modal').style.display = "none";
  }

  window.onclick = function(event) {
      if (event.target == modal) {
          modal.style.display = "none";
      }
      if (event.target == document.getElementById('navigator-modal')) {
          document.getElementById('navigator-modal').style.display = "none";
      }
      if (event.target == document.getElementById('executor-modal')) {
          document.getElementById('executor-modal').style.display = "none";
      }
      if (event.target == document.getElementById('editor-modal')) {
          document.getElementById('editor-modal').style.display = "none";
      }
      if (event.target == document.getElementById('terminal-modal')) {
          document.getElementById('terminal-modal').style.display = "none";
      }
  }

  document.getElementById('navigator').onclick = function() {
      displaySubModal('navigator-modal', 'Navigator', 'navigator');
  }

  document.getElementById('executor').onclick = function() {
      displaySubModal('executor-modal', 'Executor', 'executor');
  }

  document.getElementById('editor').onclick = function() {
      displaySubModal('editor-modal', 'Editor', 'editor');
  }

  document.getElementById('terminal').onclick = function() {
      displaySubModal('terminal-modal', 'Terminal', 'terminal');
  }

  // let response = '';

  // Handle messages sent from the extension to the webview
  // window.addEventListener("message", (event) => {
  //   const message = event.data;
  //   switch (message.type) {
  //     case "addResponse": {
  //       response = message.value;
  //       setResponse();
  //       break;
  //     }
  //     case "clearResponse": {
  //       response = '';
  //       break;
  //     }
  //     case "setPrompt": {
  //       document.getElementById("prompt-input").value = message.value;
  //       break;
  //     }
  //   }
  // });

})();

