tailwind.min.js:64 cdn.tailwindcss.com should not be used in production. To use Tailwind CSS in production, install it as a PostCSS plugin or use the Tailwind CLI: https://tailwindcss.com/docs/installation
(anonymous) @ tailwind.min.js:64
chat:30 Uncaught TypeError: Cannot read properties of null (reading 'addEventListener')
    at chat:30:23
cdn.min.js:5 Alpine Warning: You can't use [x-collapse] without first installing the "Collapse" plugin here: https://alpinejs.dev/plugins/collapse <div x-show=​"open" x-collapse class=​"ml-4 mt-2 mb-4 border-l-2 border-zinc-800 pl-4 space-y-1">​…​</div>​
E @ cdn.min.js:5
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'theme')

Expression: "$store.viewManager.theme"

 <html lang=​"en" :class=​"$store.viewManager.theme" x-data x-init=​"$store.viewManager.init()​" class>​view-source<plasmo-csui>​…​</plasmo-csui>​<head>​…​</head>​<body class=​"h-screen overflow-hidden flex">​…​</body>​flex</html>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'init')

Expression: "$store.viewManager.init()"

 <html lang=​"en" :class=​"$store.viewManager.theme" x-data x-init=​"$store.viewManager.init()​" class>​view-source<plasmo-csui>​…​</plasmo-csui>​<head>​…​</head>​<body class=​"h-screen overflow-hidden flex">​…​</body>​flex</html>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'theme')

Expression: "$store.viewManager.theme === 'dark' ? '#09090b' : '#f4f4f5'"

 <meta name=​"theme-color" id=​"theme-meta" :content=​"$store.viewManager.theme === 'dark' ? '#09090b' :​ '#f4f4f5'" content>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: sidebarOpen is not defined

Expression: "sidebarOpen ? 'translate-x-0' : '-translate-x-full'"

 <aside id=​"sidebar" class=​"fixed lg:​static inset-y-0 left-0 w-72 bg-[var(--sidebar-bg)​]​ border-r border-[var(--border-color)​]​ z-[50]​ transition-transform duration-300 transform lg:​translate-x-0" :class=​"sidebarOpen ? 'translate-x-0' :​ '-translate-x-full'">​…​</aside>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeView')

Expression: "{ 'active': $store.viewManager.activeView === 'dashboard' }"

 <a href=​"javascript:​void(0)​" class=​"nav-item" :class=​"{ 'active':​ $store.viewManager.activeView === 'dashboard' }​" hx-get=​"/​view/​dashboard" hx-target=​"#main-view-container" hx-push-url=​"true" @click=​"sidebarOpen = false">​…​</a>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeView')

Expression: "{ 'active': $store.viewManager.activeView === 'chat' }"

 <a href=​"javascript:​void(0)​" class=​"nav-item" :class=​"{ 'active':​ $store.viewManager.activeView === 'chat' }​" @click=​"open = !open;​ sidebarOpen = false" hx-get=​"/​view/​chat" hx-target=​"#main-view-container" hx-push-url=​"true">​…​</a>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeView')

Expression: "{ 'active': $store.viewManager.activeView === 'tasks' }"

 <a href=​"javascript:​void(0)​" class=​"nav-item" :class=​"{ 'active':​ $store.viewManager.activeView === 'tasks' }​" hx-get=​"/​view/​tasks" hx-target=​"#main-view-container" hx-push-url=​"true" @click=​"sidebarOpen = false">​…​</a>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeView')

Expression: "{ 'active': $store.viewManager.activeView === 'calendar' }"

 <a href=​"javascript:​void(0)​" class=​"nav-item" :class=​"{ 'active':​ $store.viewManager.activeView === 'calendar' }​" hx-get=​"/​view/​calendar" hx-target=​"#main-view-container" hx-push-url=​"true" @click=​"sidebarOpen = false">​…​</a>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeView')

Expression: "{ 'active': $store.viewManager.activeView === 'messages' }"

 <a href=​"javascript:​void(0)​" class=​"nav-item" :class=​"{ 'active':​ $store.viewManager.activeView === 'messages' }​" hx-get=​"/​view/​messages" hx-target=​"#main-view-container" hx-push-url=​"true" @click=​"sidebarOpen = false">​…​</a>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeView')

Expression: "{ 'active': $store.viewManager.activeView === 'soul' }"

 <a href=​"javascript:​void(0)​" class=​"nav-item" :class=​"{ 'active':​ $store.viewManager.activeView === 'soul' }​" hx-get=​"/​view/​soul" hx-target=​"#main-view-container" hx-push-url=​"true" @click=​"sidebarOpen = false">​…​</a>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeView')

Expression: "{ 'active': $store.viewManager.activeView === 'memory' }"

 <a href=​"javascript:​void(0)​" class=​"nav-item" :class=​"{ 'active':​ $store.viewManager.activeView === 'memory' }​" hx-get=​"/​view/​memory" hx-target=​"#main-view-container" hx-push-url=​"true" @click=​"sidebarOpen = false">​…​</a>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeView')

Expression: "{ 'active': $store.viewManager.activeView === 'api' }"

 <a href=​"javascript:​void(0)​" class=​"nav-item" :class=​"{ 'active':​ $store.viewManager.activeView === 'api' }​" hx-get=​"/​view/​api" hx-target=​"#main-view-container" hx-push-url=​"true" @click=​"sidebarOpen = false">​…​</a>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeView')

Expression: "{ 'active': $store.viewManager.activeView === 'integrations' }"

 <a href=​"javascript:​void(0)​" class=​"nav-item" :class=​"{ 'active':​ $store.viewManager.activeView === 'integrations' }​" hx-get=​"/​view/​integrations" hx-target=​"#main-view-container" hx-push-url=​"true" @click=​"sidebarOpen = false">​…​</a>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeView')

Expression: "{ 'active': $store.viewManager.activeView === 'settings' }"

 <a href=​"javascript:​void(0)​" class=​"nav-item" :class=​"{ 'active':​ $store.viewManager.activeView === 'settings' }​" hx-get=​"/​view/​settings" hx-target=​"#main-view-container" hx-push-url=​"true" @click=​"sidebarOpen = false">​…​</a>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'theme')

Expression: "$store.viewManager.theme === 'light' ? 'fas fa-sun' : 'fas fa-moon'"

 <i :class=​"$store.viewManager.theme === 'light' ? 'fas fa-sun' :​ 'fas fa-moon'" class>​</i>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'sidebarOpen')

Expression: "$store.viewManager.sidebarOpen"

 <div x-show=​"$store.viewManager.sidebarOpen" @click=​"$store.viewManager.sidebarOpen = false" x-transition:enter=​"transition ease-out duration-300" x-transition:enter-start=​"opacity-0" x-transition:enter-end=​"opacity-100" x-transition:leave=​"transition ease-in duration-200" x-transition:leave-start=​"opacity-100" x-transition:leave-end=​"opacity-0" class=​"fixed inset-0 bg-black/​60 backdrop-blur-sm z-[40]​ lg:​hidden" style=​"display:​ none;​">​</div>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'activeModal')

Expression: "$store.viewManager.activeModal === 'pairing'"

 <div x-show=​"$store.viewManager.activeModal === 'pairing'" class=​"fixed inset-0 bg-black/​80 z-[1000]​ flex items-center justify-center p-4 backdrop-blur-md" style=​"display:​ none;​">​…​</div>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'pairingToken')

Expression: "$store.viewManager.pairingToken"

 <div x-text=​"$store.viewManager.pairingToken" class=​"w-full bg-black/​40 border border-accent/​20 text-accent py-5 rounded-2xl font-mono text-center text-3xl tracking-[0.5em]​ outline-none my-4 shadow-[0_0_30px_rgba(34,197,94,0.1)​]​">​</div>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'pairingToken')

Expression: "$store.viewManager.pairingToken"

 <span x-text=​"$store.viewManager.pairingToken" class=​"font-bold text-accent">​</span>​
Bn @ cdn.min.js:1
cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'theme')
cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'init')
cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'theme')
cdn.min.js:5 Uncaught ReferenceError: sidebarOpen is not defined
10cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'activeView')
cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'theme')
cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'sidebarOpen')
cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'activeModal')
2cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'pairingToken')
cdn.min.js:1 Alpine Expression Error: window.chatInterface is not a function

Expression: "window.chatInterface()"

 <div class=​"flex flex-col h-full overflow-hidden" x-data=​"window.chatInterface()​" @refresh-chat.window=​"loadHistory()​;​ Alpine.store('viewManager')​.isStreaming = false" x-init=​"loadHistory()​">​…​</div>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: loadHistory is not defined

Expression: "loadHistory()"

 <div class=​"flex flex-col h-full overflow-hidden" x-data=​"window.chatInterface()​" @refresh-chat.window=​"loadHistory()​;​ Alpine.store('viewManager')​.isStreaming = false" x-init=​"loadHistory()​">​…​</div>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'useGlobalMemory')

Expression: "$store.viewManager.useGlobalMemory"

 <input type=​"checkbox" id=​"global-memory-toggle" class=​"sr-only peer" x-model=​"$store.viewManager.useGlobalMemory" @change=​"localStorage.setItem('use-global-memory', $store.viewManager.useGlobalMemory)​">​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: devLogOpen is not defined

Expression: "devLogOpen"

 <div x-show=​"devLogOpen" x-transition class=​"absolute inset-x-0 top-0 h-40 bg-black/​90 border-b border-zinc-800 z-20 font-mono text-[9px]​ p-4 overflow-y-auto" style=​"display:​ none;​">​…​</div>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: logs is not defined

Expression: "logs"

 <template x-for=​"log in logs">​…​</template>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: loadingHistory is not defined

Expression: "loadingHistory"

 <template x-if=​"loadingHistory">​…​</template>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: loadingHistory is not defined

Expression: "!loadingHistory && messages.length === 0"

 <template x-if=​"!loadingHistory && messages.length === 0">​…​</template>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: messages is not defined

Expression: "messages"

 <template x-for=​"(msg, index)​ in messages" :key=​"index">​…​</template>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'isStreaming')

Expression: "$store.viewManager.isStreaming"

 <template x-if=​"$store.viewManager.isStreaming">​…​</template>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'isStreaming')

Expression: "$store.viewManager.isStreaming"

 <textarea x-model=​"userInput" @keydown.enter.prevent=​"if(!$event.shiftKey)​ sendMessage()​" @input=​"$el.style.height = 'auto';​ $el.style.height = $el.scrollHeight + 'px'" class=​"w-full bg-[var(--card-bg)​]​ border border-[var(--border-color)​]​ rounded-2xl px-4 pr-14 py-4 text-[15px]​ focus:​border-accent outline-none resize-none min-h-[60px]​ max-h-[200px]​ transition-all text-white" placeholder=​"Ask your agent anything..." rows=​"1" :disabled=​"$store.viewManager.isStreaming" disabled=​"disabled">​</textarea>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: userInput is not defined

Expression: "userInput"

 <textarea x-model=​"userInput" @keydown.enter.prevent=​"if(!$event.shiftKey)​ sendMessage()​" @input=​"$el.style.height = 'auto';​ $el.style.height = $el.scrollHeight + 'px'" class=​"w-full bg-[var(--card-bg)​]​ border border-[var(--border-color)​]​ rounded-2xl px-4 pr-14 py-4 text-[15px]​ focus:​border-accent outline-none resize-none min-h-[60px]​ max-h-[200px]​ transition-all text-white" placeholder=​"Ask your agent anything..." rows=​"1" :disabled=​"$store.viewManager.isStreaming" disabled=​"disabled">​</textarea>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: userInput is not defined

Expression: "!userInput.trim() || $store.viewManager.isStreaming"

 <button type=​"submit" class=​"absolute right-2 bottom-2 w-10 h-10 bg-accent text-white rounded-xl flex items-center justify-center hover:​opacity-90 active:​scale-95 transition-all disabled:​opacity-50" :disabled=​"!userInput.trim()​ || $store.viewManager.isStreaming" disabled=​"disabled">​…​</button>​flex
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'isStreaming')

Expression: "!$store.viewManager.isStreaming"

 <i class=​"fas fa-paper-plane" x-show=​"!$store.viewManager.isStreaming" style=​"display:​ none;​">​</i>​
Bn @ cdn.min.js:1
cdn.min.js:1 Alpine Expression Error: Cannot read properties of undefined (reading 'isStreaming')

Expression: "$store.viewManager.isStreaming"

 <i class=​"fas fa-spinner fa-spin" x-show=​"$store.viewManager.isStreaming" style=​"display:​ none;​">​</i>​
Bn @ cdn.min.js:1
cdn.min.js:5 Uncaught TypeError: window.chatInterface is not a function
cdn.min.js:5 Uncaught ReferenceError: loadHistory is not defined
cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'useGlobalMemory')
cdn.min.js:5 Uncaught ReferenceError: devLogOpen is not defined
cdn.min.js:5 Uncaught ReferenceError: logs is not defined
2cdn.min.js:5 Uncaught ReferenceError: loadingHistory is not defined
cdn.min.js:5 Uncaught ReferenceError: messages is not defined
2cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'isStreaming')
2cdn.min.js:5 Uncaught ReferenceError: userInput is not defined
2cdn.min.js:5 Uncaught TypeError: Cannot read properties of undefined (reading 'isStreaming')
cdn.min.js:1 Alpine Expression Error: createNewThread is not defined

Expression: "createNewThread()"

 <button @click=​"createNewThread()​" class=​"w-full text-left px-3 py-1.5 rounded-md text-[13px]​ text-zinc-500 hover:​text-accent hover:​bg-accent/​5 transition-all flex items-center gap-2 mb-2">​…​</button>​flex
Bn @ cdn.min.js:1
cdn.min.js:5 Uncaught ReferenceError: createNewThread is not defined
cdn.min.js:1 Alpine Expression Error: createNewThread is not defined

Expression: "createNewThread()"

 <button @click=​"createNewThread()​" class=​"w-full text-left px-3 py-1.5 rounded-md text-[13px]​ text-zinc-500 hover:​text-accent hover:​bg-accent/​5 transition-all flex items-center gap-2 mb-2">​…​</button>​flex
Bn @ cdn.min.js:1
cdn.min.js:5 Uncaught ReferenceError: createNewThread is not defined