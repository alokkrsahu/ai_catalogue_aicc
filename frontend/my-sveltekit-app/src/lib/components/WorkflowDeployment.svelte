<!-- WorkflowDeployment.svelte - Workflow Deployment Component -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import { get } from 'svelte/store';
  import authStore from '$lib/stores/auth';
  
  export let project: any;
  export let projectId: string;
  
  // Component state
  let deployment: any = null;
  let workflows: any[] = [];
  let selectedWorkflowId: string = '';
  let isActive = false;
  let rateLimitPerMinute = 10;
  let allowedOrigins: any[] = [];
  let loading = false;
  let saving = false;
  
  // Origin management
  let newOrigin = '';
  let newOriginRateLimit = 10;
  let showAddOrigin = false;
  
  // Endpoint URL
  let endpointUrl = '';
  let initialGreeting = 'Hi! I am your AI assistant.';
  
  // Chatbot branding customization
  let chatbotTitle = 'AI Assistant';
  let chatbotSubtitle = 'Powered by AICC IntelliDoc';
  let primaryColor = '#78b2e8';
  let secondaryColor = '#3a6d98';
  let logoUrl = '';
  let fileUploadsEnabled = false;
  
  // Helper function to convert hex color to RGB values
  function hexToRgb(hex: string): string {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (result) {
      return `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`;
    }
    return '11, 59, 102'; // Default fallback
  }

  // Function to generate embed code with modern glassmorphism design
  function generateEmbedCode(): string {
    if (!endpointUrl || !initialGreeting) {
      console.warn('⚠️ DEPLOYMENT: Cannot generate embed code - missing endpointUrl or initialGreeting');
      return '';
    }
    const escapedEndpoint = endpointUrl.replace(/'/g, "\\'").replace(/\\/g, '\\\\');
    const escapedGreeting = JSON.stringify(initialGreeting);
    const title = chatbotTitle || 'AI Assistant';
    const subtitle = chatbotSubtitle || 'Powered by AICC IntelliDoc';
    const pColor = primaryColor || '#78b2e8';
    const sColor = secondaryColor || '#3a6d98';
    const logo = logoUrl || '';
    const primaryRgb = hexToRgb(pColor);
    const logoHtml = logo 
      ? `<img src="${logo}" alt="Logo" style="width:100%;height:100%;object-fit:cover;border-radius:12px;" />`
      : `<span style="font-size:20px;font-weight:700;color:#fff;text-transform:uppercase;">${title[0] || 'A'}</span>`;
    
    // Build HTML using array join to avoid PostCSS parsing issues
    const htmlParts: string[] = [];
    htmlParts.push('<!DOCTYPE html>');
    htmlParts.push('<html lang="en">');
    htmlParts.push('<head>');
    htmlParts.push('  <meta charset="UTF-8" />');
    htmlParts.push('  <meta name="viewport" content="width=device-width, initial-scale=1.0" />');
    htmlParts.push(`  <title>${title}</title>`);
    htmlParts.push('  <' + 'style>');
    htmlParts.push(`    :root { --primary-color: ${pColor}; --secondary-color: ${sColor}; --primary-rgb: ${primaryRgb}; --secondary-rgb: ${hexToRgb(sColor)}; }`);
    htmlParts.push('    * { box-sizing: border-box; margin: 0; padding: 0; }');
    htmlParts.push("    html, body { font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, sans-serif; background: transparent; margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; }");
    htmlParts.push('    .chat-container { width: 100%; height: 100%; background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-radius: 0; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.1); display: flex; flex-direction: column; overflow: hidden; transition: transform 0.3s ease, box-shadow 0.3s ease; }');
    htmlParts.push('    .chat-container:hover { transform: translateY(-2px); box-shadow: 0 30px 60px -12px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.15); }');
    htmlParts.push('    .chat-header { padding: 20px 24px; background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%); color: #fff; display: flex; align-items: center; gap: 14px; position: relative; overflow: hidden; }');
    htmlParts.push("    .chat-header::before { content: ''; position: absolute; top: -50%; right: -50%; width: 100%; height: 200%; background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%); pointer-events: none; }");
    htmlParts.push('    .header-logo { width: 44px; height: 44px; border-radius: 12px; background: rgba(255, 255, 255, 0.2); display: flex; align-items: center; justify-content: center; flex-shrink: 0; backdrop-filter: blur(10px); overflow: hidden; }');
    htmlParts.push('    .header-text { flex: 1; min-width: 0; }');
    htmlParts.push('    .chat-header-title { font-weight: 700; font-size: 17px; letter-spacing: -0.3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }');
    htmlParts.push('    .chat-header-sub { font-size: 12px; opacity: 0.85; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }');
    htmlParts.push('    .online-indicator { width: 10px; height: 10px; background: #22c55e; border-radius: 50%; box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.3); animation: pulse 2s infinite; }');
    htmlParts.push('    @keyframes pulse { 0%, 100% { box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.3); } 50% { box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.1); } }');
    htmlParts.push('    .chat-messages { flex: 1; padding: 20px; overflow-y: auto; background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%); font-size: 14px; scroll-behavior: smooth; }');
    htmlParts.push('    .chat-messages { scrollbar-gutter: stable; }');
    htmlParts.push('    .chat-messages::-webkit-scrollbar { width: 7px; }');
    htmlParts.push('    .chat-messages::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.03); }');
    htmlParts.push('    .chat-messages::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.15); border-radius: 4px; }');
    htmlParts.push('    .chat-messages::-webkit-scrollbar-thumb:hover { background: rgba(0, 0, 0, 0.25); }');
    htmlParts.push('    .msg { margin-bottom: 16px; display: flex; animation: slideIn 0.3s ease-out; }');
    htmlParts.push('    @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }');
    htmlParts.push('    .msg.user { justify-content: flex-end; }');
    htmlParts.push('    .msg.assistant { justify-content: flex-start; }');
    htmlParts.push('    .bubble { max-width: 85%; padding: 12px 16px; border-radius: 18px; line-height: 1.5; position: relative; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06); }');
    htmlParts.push('    .msg.user .bubble { background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%); color: #fff; border-bottom-right-radius: 6px; }');
    htmlParts.push('    .msg.assistant .bubble { background: #ffffff; color: #1e293b; border: 1px solid rgba(0, 0, 0, 0.06); border-bottom-left-radius: 6px; }');
    htmlParts.push('    .chat-input-container { padding: 16px 20px 20px; background: #ffffff; border-top: 1px solid rgba(0, 0, 0, 0.06); }');
    htmlParts.push('    .chat-input { display: flex; align-items: flex-end; gap: 12px; background: #f1f5f9; border-radius: 16px; padding: 8px 8px 8px 16px; transition: box-shadow 0.2s ease, background 0.2s ease; }');
    htmlParts.push('    .chat-input:focus-within { background: #fff; box-shadow: 0 0 0 2px var(--primary-color), 0 4px 12px rgba(var(--primary-rgb), 0.15); }');
    htmlParts.push('    .chat-input textarea { flex: 1; resize: none; border: none; background: transparent; padding: 8px 0; font-size: 14px; line-height: 1.5; color: #1e293b; font-family: inherit; min-height: 24px; max-height: 120px; overflow-y: auto; }');
    htmlParts.push('    .chat-input textarea::placeholder { color: #94a3b8; }');
    htmlParts.push('    .chat-input textarea:focus { outline: none; }');
    htmlParts.push('    .chat-input button { width: 40px; height: 40px; background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%); color: #fff; border: none; border-radius: 12px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: transform 0.2s ease, box-shadow 0.2s ease; flex-shrink: 0; }');
    htmlParts.push('    .chat-input button:hover:not(:disabled) { transform: scale(1.05); box-shadow: 0 4px 12px rgba(var(--primary-rgb), 0.4); }');
    htmlParts.push('    .chat-input button:active:not(:disabled) { transform: scale(0.95); }');
    htmlParts.push('    .chat-input button:disabled { opacity: 0.5; cursor: not-allowed; }');
    htmlParts.push('    .chat-input button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }');
    htmlParts.push('    .chat-input button svg { width: 20px; height: 20px; transition: transform 0.2s ease; }');
    htmlParts.push('    .chat-input button:hover:not(:disabled) svg { transform: translateX(2px); }');
    htmlParts.push('    .status { font-size: 11px; color: #64748b; padding: 8px 20px 0; text-align: center; }');
    htmlParts.push('    .human-input-modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); z-index: 1000; justify-content: center; align-items: center; padding: 16px; }');
    htmlParts.push('    .human-input-modal.active { display: flex; }');
    htmlParts.push('    .human-input-box { background: #fff; border-radius: 20px; padding: 28px; max-width: 480px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4); animation: modalSlideIn 0.3s ease-out; }');
    htmlParts.push('    @keyframes modalSlideIn { from { opacity: 0; transform: scale(0.95) translateY(10px); } to { opacity: 1; transform: scale(1) translateY(0); } }');
    htmlParts.push("    .human-input-title { font-size: 18px; font-weight: 700; color: var(--primary-color); margin-bottom: 16px; display: flex; align-items: center; gap: 10px; }");
    htmlParts.push("    .human-input-title::before { content: ''; width: 4px; height: 20px; background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%); border-radius: 2px; }");
    htmlParts.push('    .human-input-message { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 20px; font-size: 14px; color: #475569; line-height: 1.6; }');
    htmlParts.push('    .human-input-textarea { width: 100%; min-height: 100px; border: 2px solid #e2e8f0; border-radius: 12px; padding: 14px; font-size: 14px; resize: vertical; font-family: inherit; transition: border-color 0.2s ease, box-shadow 0.2s ease; }');
    htmlParts.push('    .human-input-textarea:focus { outline: none; border-color: var(--primary-color); box-shadow: 0 0 0 3px rgba(var(--primary-rgb), 0.1); }');
    htmlParts.push('    .human-input-buttons { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; }');
    htmlParts.push('    .human-input-buttons button { padding: 12px 24px; border-radius: 12px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; transition: all 0.2s ease; }');
    htmlParts.push('    .human-input-buttons .submit-btn { background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%); color: #fff; }');
    htmlParts.push('    .human-input-buttons .submit-btn:hover:not(:disabled) { box-shadow: 0 4px 12px rgba(var(--primary-rgb), 0.4); transform: translateY(-1px); }');
    htmlParts.push('    .human-input-buttons .submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }');
    htmlParts.push('    .human-input-buttons .cancel-btn { background: #f1f5f9; color: #475569; }');
    htmlParts.push('    .human-input-buttons .cancel-btn:hover { background: #e2e8f0; }');
    htmlParts.push('    .thinking-indicator { display: flex; align-items: center; gap: 8px; padding: 12px 16px; }');
    htmlParts.push('    .thinking-dots { display: flex; gap: 5px; }');
    htmlParts.push('    .thinking-dot { width: 8px; height: 8px; background: var(--primary-color); border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }');
    htmlParts.push('    .thinking-dot:nth-child(1) { animation-delay: -0.32s; }');
    htmlParts.push('    .thinking-dot:nth-child(2) { animation-delay: -0.16s; }');
    htmlParts.push('    .thinking-dot:nth-child(3) { animation-delay: 0s; }');
    htmlParts.push('    @keyframes bounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }');
    htmlParts.push('    .bubble markdown { display: block; }');
    htmlParts.push('    .bubble markdown p { margin: 8px 0; }');
    htmlParts.push('    .bubble markdown p:first-child { margin-top: 0; }');
    htmlParts.push('    .bubble markdown p:last-child { margin-bottom: 0; }');
    htmlParts.push('    .bubble markdown strong { font-weight: 600; }');
    htmlParts.push('    .bubble markdown em { font-style: italic; }');
    htmlParts.push("    .bubble markdown code { background: rgba(0, 0, 0, 0.06); padding: 2px 6px; border-radius: 4px; font-family: 'SF Mono', 'Consolas', monospace; font-size: 0.875em; }");
    htmlParts.push('    .msg.user .bubble markdown code { background: rgba(255, 255, 255, 0.2); }');
    htmlParts.push('    .bubble markdown pre { background: #1e293b; color: #e2e8f0; padding: 14px; border-radius: 10px; overflow-x: auto; margin: 10px 0; }');
    htmlParts.push('    .bubble markdown pre code { background: none; padding: 0; color: inherit; }');
    htmlParts.push('    .bubble markdown ul, .bubble markdown ol { margin: 8px 0; padding-left: 24px; }');
    htmlParts.push('    .bubble markdown li { margin: 4px 0; }');
    htmlParts.push('    .bubble markdown blockquote { border-left: 3px solid var(--primary-color); padding-left: 12px; margin: 10px 0; color: #64748b; font-style: italic; }');
    htmlParts.push('    .bubble markdown a { color: var(--primary-color); text-decoration: underline; }');
    htmlParts.push('    .msg.user .bubble markdown a { color: #fff; }');
    htmlParts.push('    .bubble markdown h1 { font-size: 1.4em; font-weight: 700; margin: 14px 0 8px; }');
    htmlParts.push('    .bubble markdown h2 { font-size: 1.25em; font-weight: 700; margin: 12px 0 6px; }');
    htmlParts.push('    .bubble markdown h3 { font-size: 1.1em; font-weight: 600; margin: 10px 0 4px; }');
    htmlParts.push('    .bubble markdown hr { border: none; border-top: 1px solid #e2e8f0; margin: 12px 0; }');
    // Citation chips & tooltips
    htmlParts.push('    .cite-chip { display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px; padding: 0 4px; border-radius: 4px; background: var(--primary-color, #0ea5e9); color: white; font-size: 11px; font-weight: 600; cursor: pointer; vertical-align: super; margin: 0 1px; line-height: 1; transition: background 0.15s; }');
    htmlParts.push('    .cite-chip:hover { filter: brightness(0.85); }');
    htmlParts.push('    .cite-chip-secondary { background: #e5e7eb; color: #374151; cursor: default; }');
    htmlParts.push('    .cite-chip-secondary:hover { filter: none; }');
    htmlParts.push('    .cite-tooltip { position: fixed; max-width: 340px; background: #1e293b; color: #e2e8f0; border-radius: 8px; padding: 10px 14px; font-size: 13px; box-shadow: 0 8px 24px rgba(0,0,0,0.3); z-index: 9999; animation: citeIn 0.15s ease-out; }');
    htmlParts.push('    .cite-tooltip-title { font-weight: 600; color: #38bdf8; margin-bottom: 6px; font-size: 12px; }');
    htmlParts.push('    .cite-tooltip-link { color: #38bdf8; text-decoration: underline; text-underline-offset: 2px; cursor: pointer; transition: color 0.15s; }');
    htmlParts.push('    .cite-tooltip-link:hover { color: #7dd3fc; }');
    htmlParts.push('    .cite-tooltip-source { font-size: 11px; color: #94a3b8; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }');
    htmlParts.push('    .cite-tooltip-quote { font-style: italic; color: #cbd5e1; font-size: 12px; line-height: 1.5; }');
    htmlParts.push('    @keyframes citeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }');
    // Activity / Planning panel
    htmlParts.push('    .activity-panel { background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 12px; margin: 0 16px 6px 56px; overflow: hidden; transition: max-height 0.35s ease, opacity 0.25s ease; max-height: 320px; opacity: 1; }');
    htmlParts.push('    .activity-panel.collapsed { max-height: 32px; cursor: pointer; }');
    htmlParts.push('    .activity-header { display: flex; align-items: center; gap: 6px; padding: 6px 12px; font-size: 12px; font-weight: 600; color: #64748b; user-select: none; cursor: pointer; }');
    htmlParts.push('    .activity-header svg { width: 14px; height: 14px; flex-shrink: 0; transition: transform 0.25s; }');
    htmlParts.push('    .activity-panel.collapsed .activity-header svg { transform: rotate(-90deg); }');
    htmlParts.push('    .activity-items { max-height: 260px; overflow-y: auto; padding: 0 12px 8px; }');
    htmlParts.push('    .activity-panel.collapsed .activity-items { display: none; }');
    htmlParts.push('    .activity-item { display: flex; align-items: flex-start; gap: 8px; padding: 5px 0; font-size: 12px; color: #475569; line-height: 1.45; border-bottom: 1px solid #e2e8f0; animation: actItemIn 0.2s ease-out; }');
    htmlParts.push('    .activity-item:last-child { border-bottom: none; }');
    htmlParts.push('    .activity-item-icon { flex-shrink: 0; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; border-radius: 4px; font-size: 11px; }');
    htmlParts.push('    .activity-item-body b { color: #334155; }');
    htmlParts.push('    .activity-item.expandable { cursor: pointer; flex-wrap: wrap; }');
    htmlParts.push('    .activity-item.expandable:hover { background: #e2e8f0; border-radius: 6px; }');
    htmlParts.push("    .activity-item.expandable .activity-item-body::after { content: ' \\25B8'; font-size: 10px; color: #94a3b8; transition: transform 0.2s; }");
    htmlParts.push("    .activity-item.expanded .activity-item-body::after { content: ' \\25BE'; }");
    htmlParts.push("    .activity-detail { display: none; width: 100%; margin-top: 4px; padding: 8px 10px; background: #e8ecf1; border-radius: 6px; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; font-size: 11px; line-height: 1.55; color: #334155; white-space: pre-wrap; word-break: break-word; max-height: 180px; overflow-y: auto; animation: detailSlide 0.2s ease-out; }");
    htmlParts.push('    .activity-item.expanded .activity-detail { display: block; }');
    htmlParts.push('    @keyframes detailSlide { from { opacity: 0; max-height: 0; } to { opacity: 1; max-height: 180px; } }');
    htmlParts.push('    @keyframes actItemIn { from { opacity: 0; transform: translateX(-6px); } to { opacity: 1; transform: translateX(0); } }');
    htmlParts.push('  </' + 'style>');
    htmlParts.push('</head>');
    htmlParts.push('<body>');
    htmlParts.push('<div class="chat-container">');
    htmlParts.push('  <div class="chat-header">');
    htmlParts.push(`    <div class="header-logo">${logoHtml}</div>`);
    htmlParts.push('    <div class="header-text">');
    htmlParts.push(`      <div class="chat-header-title">${title}</div>`);
    htmlParts.push(`      <div class="chat-header-sub">${subtitle}</div>`);
    htmlParts.push('    </div>');
    htmlParts.push('    <div class="online-indicator"></div>');
    htmlParts.push('  </div>');
    htmlParts.push('  <div id="messages" class="chat-messages"></div>');
    htmlParts.push('  <div id="status" class="status"></div>');
    htmlParts.push('  <div class="chat-input-container">');
    htmlParts.push('    <div class="chat-input">');
    htmlParts.push('      <textarea id="input" rows="1" placeholder="Type your message..."></textarea>');
    htmlParts.push('      <button id="sendBtn" title="Send message">');
    htmlParts.push('        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">');
    htmlParts.push('          <line x1="22" y1="2" x2="11" y2="13"></line>');
    htmlParts.push('          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>');
    htmlParts.push('        </svg>');
    htmlParts.push('      </button>');
    htmlParts.push('    </div>');
    htmlParts.push('  </div>');
    htmlParts.push('</div>');
    htmlParts.push('');
    htmlParts.push('<!-- Human Input Modal -->');
    htmlParts.push('<div id="humanInputModal" class="human-input-modal">');
    htmlParts.push('  <div class="human-input-box">');
    htmlParts.push('    <div class="human-input-title" id="humanInputTitle">Input Required</div>');
    htmlParts.push('    <div class="human-input-message" id="humanInputMessage"></div>');
    htmlParts.push('    <textarea id="humanInputTextarea" class="human-input-textarea" placeholder="Enter your response..."></textarea>');
    htmlParts.push('    <div class="human-input-buttons">');
    htmlParts.push('      <button class="cancel-btn" id="humanInputCancel">Cancel</button>');
    htmlParts.push('      <button class="submit-btn" id="humanInputSubmit">Submit</button>');
    htmlParts.push('    </div>');
    htmlParts.push('  </div>');
    htmlParts.push('</div>');
    htmlParts.push('');
    htmlParts.push('<' + 'script>');
    htmlParts.push('  const ENDPOINT_URL = \'' + escapedEndpoint + '\';');
    htmlParts.push("  const STREAM_URL = ENDPOINT_URL.replace(/\\/$/, '') + '/stream/';");
    htmlParts.push("  const SUBMIT_INPUT_URL = ENDPOINT_URL.replace(/\\/$/, '') + '/submit-input/';");
    htmlParts.push('  const INITIAL_GREETING = ' + escapedGreeting + ';');
    htmlParts.push('');
    htmlParts.push('  // Enhanced markdown renderer');
    htmlParts.push('  function renderMarkdown(text) {');
    htmlParts.push("    if (!text) return '';");
    htmlParts.push('    let html = text');
    htmlParts.push("      .replace(/&/g, '&amp;')");
    htmlParts.push("      .replace(/</g, '&lt;')");
    htmlParts.push("      .replace(/>/g, '&gt;');");
    htmlParts.push("    html = html.replace(/^######\\s+(.+)$/gm, '<h6>$1</h6>');");
    htmlParts.push("    html = html.replace(/^#####\\s+(.+)$/gm, '<h5>$1</h5>');");
    htmlParts.push("    html = html.replace(/^####\\s+(.+)$/gm, '<h4>$1</h4>');");
    htmlParts.push("    html = html.replace(/^###\\s+(.+)$/gm, '<h3>$1</h3>');");
    htmlParts.push("    html = html.replace(/^##\\s+(.+)$/gm, '<h2>$1</h2>');");
    htmlParts.push("    html = html.replace(/^#\\s+(.+)$/gm, '<h1>$1</h1>');");
    htmlParts.push("    html = html.replace(/^\\s*[-*]{3,}\\s*$/gm, '<hr>');");
    htmlParts.push("    html = html.replace(/```(\\w+)?[\\n\\r]+([\\s\\S]*?)```/g, function(match, lang, code) {");
    htmlParts.push("      return '<pre><code>' + code.trim() + '</code></pre>';");
    htmlParts.push('    });');
    htmlParts.push("    html = html.replace(/^>\\s+(.+)$/gm, '<blockquote>$1</blockquote>');");
    htmlParts.push("    const lines = html.split('\\n');");
    htmlParts.push('    const processedLines = [];');
    htmlParts.push('    let inOrderedList = false;');
    htmlParts.push('    let inUnorderedList = false;');
    htmlParts.push('    for (let i = 0; i < lines.length; i++) {');
    htmlParts.push('      const line = lines[i];');
    htmlParts.push('      const orderedMatch = line.match(/^(\\d+)\\.\\s+(.+)$/);');
    htmlParts.push('      const unorderedMatch = line.match(/^[-*]\\s+(.+)$/);');
    htmlParts.push('      if (orderedMatch) {');
    htmlParts.push('        if (!inOrderedList) {');
    htmlParts.push("          if (inUnorderedList) { processedLines.push('</ul>'); inUnorderedList = false; }");
    htmlParts.push("          processedLines.push('<ol>');");
    htmlParts.push('          inOrderedList = true;');
    htmlParts.push('        }');
    htmlParts.push("        processedLines.push('<li>' + orderedMatch[2] + '</li>');");
    htmlParts.push('      } else if (unorderedMatch) {');
    htmlParts.push('        if (!inUnorderedList) {');
    htmlParts.push("          if (inOrderedList) { processedLines.push('</ol>'); inOrderedList = false; }");
    htmlParts.push("          processedLines.push('<ul>');");
    htmlParts.push('          inUnorderedList = true;');
    htmlParts.push('        }');
    htmlParts.push("        processedLines.push('<li>' + unorderedMatch[1] + '</li>');");
    htmlParts.push('      } else {');
    htmlParts.push("        if (inOrderedList) { processedLines.push('</ol>'); inOrderedList = false; }");
    htmlParts.push("        if (inUnorderedList) { processedLines.push('</ul>'); inUnorderedList = false; }");
    htmlParts.push('        processedLines.push(line);');
    htmlParts.push('      }');
    htmlParts.push('    }');
    htmlParts.push("    if (inOrderedList) processedLines.push('</ol>');");
    htmlParts.push("    if (inUnorderedList) processedLines.push('</ul>');");
    htmlParts.push("    html = processedLines.join('\\n');");
    htmlParts.push("    html = html.replace(/\\[([^\\]]+)\\]\\(([^\\)]+)\\)/g, '<a href=\"$2\" target=\"_blank\" rel=\"noopener\">$1</a>');");
    htmlParts.push("    html = html.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');");
    htmlParts.push("    html = html.replace(/__(?!_)([^_]+)__/g, '<strong>$1</strong>');");
    htmlParts.push("    html = html.replace(/\\*(?!\\*)([^*]+)\\*(?!\\*)/g, '<em>$1</em>');");
    htmlParts.push("    html = html.replace(/_(?!_)([^_]+)_(?!_)/g, '<em>$1</em>');");
    htmlParts.push("    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');");
    htmlParts.push("    const paragraphs = html.split(/\\n\\n+/);");
    htmlParts.push('    html = paragraphs.map(function(p) {');
    htmlParts.push('      p = p.trim();');
    htmlParts.push("      if (!p) return '';");
    htmlParts.push("      if (/^<(pre|blockquote|ul|ol|hr|h[1-6])/i.test(p)) return p;");
    htmlParts.push("      p = p.replace(/\\n/g, '<br>');");
    htmlParts.push("      return '<p>' + p + '</p>';");
    htmlParts.push("    }).filter(function(p) { return p; }).join('');");
    htmlParts.push('    return html;');
    htmlParts.push('  }');
    htmlParts.push('');
    // --- Citation parsing & rendering ---
    htmlParts.push('  function parseCitations(text) {');
    htmlParts.push('    var pattern = /---CITATIONS---\\s*([\\s\\S]*?)\\s*---END_CITATIONS---/;');
    htmlParts.push('    var m = text.match(pattern);');
    htmlParts.push('    if (!m) return { cleanText: text, citations: [] };');
    htmlParts.push('    var cleanText = text.slice(0, m.index).trim();');
    htmlParts.push('    cleanText = cleanText.replace(/[\\n\\r]+(?:#{1,6}\\s*)?(?:\\*{1,2})?CITATIONS(?:\\*{1,2})?\\s*$/i, "").trim();');
    htmlParts.push('    var citations = [];');
    htmlParts.push('    try {');
    htmlParts.push('      citations = JSON.parse(m[1].trim());');
    htmlParts.push('      if (!Array.isArray(citations)) citations = [];');
    htmlParts.push('      else citations = citations.filter(function(c) {');
    htmlParts.push('        if (!c || typeof c !== "object") return false;');
    htmlParts.push('        var r = parseInt(c.ref, 10);');
    htmlParts.push('        if (isNaN(r)) return false;');
    htmlParts.push('        c.ref = r;');
    htmlParts.push('        return true;');
    htmlParts.push('      });');
    htmlParts.push('    } catch(e) { citations = []; }');
    htmlParts.push('    return { cleanText: cleanText, citations: citations };');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function renderCitationChips(html, citations) {');
    htmlParts.push('    if (!citations || citations.length === 0) return html;');
    htmlParts.push('    return html.replace(/\\[(\\d+)\\]/g, function(match, num) {');
    htmlParts.push('      var ref = parseInt(num, 10);');
    htmlParts.push('      var cit = citations.find(function(c) { return Number(c.ref) === ref; });');
    htmlParts.push("      if (!cit) return '<span class=\"cite-chip cite-chip-secondary\" data-ref=\"' + ref + '\">' + ref + '</span>';");
    htmlParts.push("      return '<span class=\"cite-chip\" data-ref=\"' + ref + '\">' + ref + '</span>';");
    htmlParts.push('    });');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  var _chatCitations = [];');
    htmlParts.push('  var _activeCiteTooltip = null;');
    htmlParts.push('');
    htmlParts.push('  function showCiteTooltip(chipEl, ref) {');
    htmlParts.push('    if (_activeCiteTooltip) { _activeCiteTooltip.remove(); _activeCiteTooltip = null; }');
    htmlParts.push('    var cit = _chatCitations.find(function(c) { return Number(c.ref) === ref; });');
    htmlParts.push('    if (!cit) return;');
    htmlParts.push("    var tip = document.createElement('div');");
    htmlParts.push("    tip.className = 'cite-tooltip';");
    htmlParts.push("    var isWeb = cit.url || cit.source === 'web';");
    htmlParts.push('    var titleHtml;');
    htmlParts.push('    if (isWeb && cit.url) {');
    htmlParts.push("      var safeUrl = cit.url.replace(/\"/g, '&quot;').replace(/</g, '&lt;');");
    htmlParts.push("      titleHtml = '<a class=\"cite-tooltip-link\" href=\"' + safeUrl + '\" target=\"_blank\" rel=\"noopener\">' + (cit.document_title || cit.url).replace(/</g, '&lt;') + '</a>';");
    htmlParts.push('    } else {');
    htmlParts.push("      var loc = '';");
    htmlParts.push("      if (cit.page) loc += 'p.' + cit.page;");
    htmlParts.push("      if (cit.section) loc += (loc ? ', ' : '') + cit.section;");
    htmlParts.push("      titleHtml = '<a class=\"cite-tooltip-link\" href=\"#\" data-docid=\"' + (cit.document_id || '') + '\">' + (cit.document_title || 'Source').replace(/</g, '&lt;') + (loc ? ' \\u2014 ' + loc : '') + '</a>';");
    htmlParts.push('    }');
    htmlParts.push("    var sourceHtml = '';");
    htmlParts.push('    if (isWeb && cit.url) {');
    htmlParts.push('      try {');
    htmlParts.push("        var domain = new URL(cit.url).hostname.replace(/^www\\\\./, '');");
    htmlParts.push("        sourceHtml = '<div class=\"cite-tooltip-source\">\\uD83C\\uDF10 ' + domain.replace(/</g, '&lt;') + '</div>';");
    htmlParts.push('      } catch(_e) {');
    htmlParts.push("        sourceHtml = '<div class=\"cite-tooltip-source\">\\uD83C\\uDF10 Web</div>';");
    htmlParts.push('      }');
    htmlParts.push('    }');
    htmlParts.push("    tip.innerHTML = '<div class=\"cite-tooltip-title\">' + titleHtml + '</div>' + sourceHtml + '<div class=\"cite-tooltip-quote\">\\u201C' + ((cit.quoted_text || '').slice(0, 300).replace(/</g,'&lt;')) + '\\u201D</div>';");
    htmlParts.push('    document.body.appendChild(tip);');
    htmlParts.push('    var rect = chipEl.getBoundingClientRect();');
    htmlParts.push("    tip.style.left = Math.min(rect.left, window.innerWidth - tip.offsetWidth - 8) + 'px';");
    htmlParts.push("    tip.style.top = (rect.bottom + 6) + 'px';");
    htmlParts.push('    _activeCiteTooltip = tip;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push("  document.addEventListener('click', function(e) {");
    htmlParts.push("    var link = e.target.closest && e.target.closest('.cite-tooltip-link');");
    htmlParts.push('    if (link) {');
    htmlParts.push("      if (link.dataset.docid) { e.preventDefault(); openCitationDocument(link.dataset.docid); return; }");
    htmlParts.push("      if (link.href && link.target === '_blank') { return; }");
    htmlParts.push('    }');
    htmlParts.push("    var chip = e.target.closest && e.target.closest('.cite-chip');");
    htmlParts.push('    if (chip) {');
    htmlParts.push("      var ref = parseInt(chip.dataset.ref, 10);");
    htmlParts.push("      if (_activeCiteTooltip && _activeCiteTooltip._ref === ref) {");
    htmlParts.push('        _activeCiteTooltip.remove(); _activeCiteTooltip = null;');
    htmlParts.push('      } else {');
    htmlParts.push('        showCiteTooltip(chip, ref);');
    htmlParts.push('        if (_activeCiteTooltip) _activeCiteTooltip._ref = ref;');
    htmlParts.push('      }');
    htmlParts.push('    } else if (_activeCiteTooltip) {');
    htmlParts.push('      _activeCiteTooltip.remove(); _activeCiteTooltip = null;');
    htmlParts.push('    }');
    htmlParts.push('  });');
    htmlParts.push('');
    htmlParts.push('  const messages = [];');
    htmlParts.push("  var _urlParams = new URLSearchParams(window.location.search || '');");
    htmlParts.push("  var _urlSessId = (_urlParams.get('session_id') || '').trim();");
    htmlParts.push("  const sessionId = _urlSessId || ('sess_' + Math.random().toString(36).slice(2));");
    htmlParts.push(`  const PROJECT_ID = '${projectId}';`);
    htmlParts.push('');
    htmlParts.push('  function _getCiteAuthHeaders() {');
    htmlParts.push("    try { var _a = localStorage.getItem('auth'); if (_a) { var _p = JSON.parse(_a); if (_p && _p.token) return { 'Authorization': 'Bearer ' + _p.token }; } } catch(_) {}");
    htmlParts.push('    return {};');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function openCitationDocument(documentId) {');
    htmlParts.push("    if (!PROJECT_ID || !documentId) return;");
    htmlParts.push("    fetch('/api/projects/' + PROJECT_ID + '/documents/' + documentId + '/download/', { headers: _getCiteAuthHeaders() })");
    htmlParts.push("      .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.blob(); })");
    htmlParts.push("      .then(function(blob) { var u = URL.createObjectURL(blob); window.open(u, '_blank'); setTimeout(function() { URL.revokeObjectURL(u); }, 60000); })");
    htmlParts.push("      .catch(function(err) { console.error('Citation document open failed:', err); });");
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  var _historyPreloaded = false;');
    htmlParts.push('  (async function() {');
    htmlParts.push("    if (!PROJECT_ID || !sessionId) return;");
    htmlParts.push('    try {');
    htmlParts.push("      var url = '/api/agent-orchestration/projects/' + PROJECT_ID + '/deployment/activity/?session_id=' + encodeURIComponent(sessionId) + '&limit=1';");
    htmlParts.push("      var resp = await fetch(url, { credentials: 'include', headers: _getCiteAuthHeaders() });");
    htmlParts.push('      if (!resp.ok) return;');
    htmlParts.push("      var data = await resp.json().catch(function() { return null; });");
    htmlParts.push("      if (!data || !Array.isArray(data.sessions) || !data.sessions.length) return;");
    htmlParts.push("      var history = Array.isArray(data.sessions[0].conversation_history) ? data.sessions[0].conversation_history : [];");
    htmlParts.push('      var recent = history.slice(-100);');
    htmlParts.push('      if (!recent.length) return;');
    htmlParts.push('      _historyPreloaded = true;');
    htmlParts.push('      for (var i = 0; i < recent.length; i++) {');
    htmlParts.push('        var m = recent[i];');
    htmlParts.push("        if (!m || !m.role || typeof m.content !== 'string') continue;");
    htmlParts.push("        appendMessage(m.role === 'user' ? 'user' : 'assistant', m.content, false, Array.isArray(m.citations) ? m.citations : undefined);");
    htmlParts.push("        messages.push({ role: m.role, content: m.content });");
    htmlParts.push('      }');
    htmlParts.push('    } catch(_e) {}');
    htmlParts.push('  })().then(function() {');
    htmlParts.push('    if (!_historyPreloaded) {');
    htmlParts.push('      appendMessage(\'assistant\', INITIAL_GREETING);');
    htmlParts.push("      messages.push({ role: 'assistant', content: INITIAL_GREETING });");
    htmlParts.push('    }');
    htmlParts.push('  });');
    htmlParts.push('  let currentExecutionId = null;');
    htmlParts.push('  let awaitingHumanInput = false;');
    htmlParts.push('');
    htmlParts.push("  const messagesEl = document.getElementById('messages');");
    htmlParts.push("  const inputEl = document.getElementById('input');");
    htmlParts.push("  const sendBtn = document.getElementById('sendBtn');");
    htmlParts.push("  const statusEl = document.getElementById('status');");
    htmlParts.push("  const humanInputModal = document.getElementById('humanInputModal');");
    htmlParts.push("  const humanInputTitle = document.getElementById('humanInputTitle');");
    htmlParts.push("  const humanInputMessage = document.getElementById('humanInputMessage');");
    htmlParts.push("  const humanInputTextarea = document.getElementById('humanInputTextarea');");
    htmlParts.push("  const humanInputSubmit = document.getElementById('humanInputSubmit');");
    htmlParts.push("  const humanInputCancel = document.getElementById('humanInputCancel');");
    htmlParts.push('');
    htmlParts.push('  // Auto-resize textarea');
    htmlParts.push('  function autoResize() {');
    htmlParts.push("    inputEl.style.height = 'auto';");
    htmlParts.push("    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';");
    htmlParts.push('  }');
    htmlParts.push("  inputEl.addEventListener('input', autoResize);");
    htmlParts.push('');
    htmlParts.push('  function appendMessage(role, text, isStreaming = false, apiCitations) {');
    htmlParts.push("    const msg = document.createElement('div');");
    htmlParts.push("    msg.className = 'msg ' + (role === 'user' ? 'user' : 'assistant');");
    htmlParts.push("    const bubble = document.createElement('div');");
    htmlParts.push("    bubble.className = 'bubble';");
    htmlParts.push("    if (role === 'assistant' && !isStreaming) {");
    htmlParts.push('      var parsed = parseCitations(text); var cleanText = parsed.cleanText;');
    htmlParts.push('      var citations = [];');
    htmlParts.push('      if (Array.isArray(apiCitations) && apiCitations.length > 0) { citations = apiCitations; }');
    htmlParts.push('      else { citations = parsed.citations; }');
    htmlParts.push('      if (citations.length > 0) _chatCitations = citations;');
    htmlParts.push("      const markdownEl = document.createElement('markdown');");
    htmlParts.push('      var rendered = renderMarkdown(cleanText);');
    htmlParts.push('      if (citations.length > 0) rendered = renderCitationChips(rendered, citations);');
    htmlParts.push('      markdownEl.innerHTML = rendered;');
    htmlParts.push('      bubble.appendChild(markdownEl);');
    htmlParts.push('    } else {');
    htmlParts.push('      bubble.textContent = text;');
    htmlParts.push('    }');
    htmlParts.push('    msg.appendChild(bubble);');
    htmlParts.push('    messagesEl.appendChild(msg);');
    htmlParts.push('    messagesEl.scrollTop = messagesEl.scrollHeight;');
    htmlParts.push('    return bubble;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function showThinkingIndicator() {');
    htmlParts.push("    const msg = document.createElement('div');");
    htmlParts.push("    msg.className = 'msg assistant';");
    htmlParts.push("    msg.id = 'thinking-indicator';");
    htmlParts.push("    const indicator = document.createElement('div');");
    htmlParts.push("    indicator.className = 'thinking-indicator';");
    htmlParts.push("    indicator.innerHTML = '<div class=\"thinking-dots\"><div class=\"thinking-dot\"></div><div class=\"thinking-dot\"></div><div class=\"thinking-dot\"></div></div>';");
    htmlParts.push('    msg.appendChild(indicator);');
    htmlParts.push('    messagesEl.appendChild(msg);');
    htmlParts.push('    messagesEl.scrollTop = messagesEl.scrollHeight;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function hideThinkingIndicator() {');
    htmlParts.push("    const indicator = document.getElementById('thinking-indicator');");
    htmlParts.push('    if (indicator) indicator.remove();');
    htmlParts.push('  }');
    htmlParts.push('');
    // --- Activity / Planning panel ---
    htmlParts.push('  var _activityPanel = null, _activityItems = null, _activityHeader = null, _activityStartTs = null;');
    htmlParts.push("  var _activityIcons = { planning: '\\uD83D\\uDCCB', delegate_start: '\\uD83E\\uDD1D', delegate_plan: '\\uD83D\\uDCDD', tool_result: '\\uD83D\\uDD0D', delegate_done: '\\u2705', synthesizing: '\\u2699\\uFE0F' };");
    htmlParts.push('  function _ensureActivityPanel() {');
    htmlParts.push('    if (_activityPanel) return;');
    htmlParts.push('    _activityStartTs = Date.now();');
    htmlParts.push("    _activityPanel = document.createElement('div');");
    htmlParts.push("    _activityPanel.className = 'activity-panel';");
    htmlParts.push("    _activityHeader = document.createElement('div');");
    htmlParts.push("    _activityHeader.className = 'activity-header';");
    htmlParts.push("    _activityHeader.innerHTML = '<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\"><polyline points=\"6 9 12 15 18 9\"></polyline></svg><span>Processing\\u2026</span>';");
    htmlParts.push("    var panelRef = _activityPanel;");
    htmlParts.push("    _activityHeader.addEventListener('click', function() { panelRef.classList.toggle('collapsed'); });");
    htmlParts.push("    _activityItems = document.createElement('div');");
    htmlParts.push("    _activityItems.className = 'activity-items';");
    htmlParts.push('    _activityPanel.appendChild(_activityHeader);');
    htmlParts.push('    _activityPanel.appendChild(_activityItems);');
    htmlParts.push("    var thinkingEl = document.getElementById('thinking-indicator');");
    htmlParts.push('    if (thinkingEl) { thinkingEl.parentNode.insertBefore(_activityPanel, thinkingEl); thinkingEl.remove(); }');
    htmlParts.push('    else { messagesEl.appendChild(_activityPanel); }');
    htmlParts.push('    messagesEl.scrollTop = messagesEl.scrollHeight;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function showActivityItem(data) {');
    htmlParts.push('    _ensureActivityPanel();');
    htmlParts.push("    var icon = _activityIcons[data.type] || '\\u2022';");
    htmlParts.push("    var desc = '';");
    htmlParts.push("    switch (data.type) {");
    htmlParts.push("      case 'planning': desc = '<b>' + (data.agent || '') + '</b> created a plan'; break;");
    htmlParts.push("      case 'delegate_start': desc = '<b>' + (data.agent || '') + '</b> started \\u2014 ' + (Array.isArray(data.tasks) ? data.tasks.length + ' task(s)' : ''); break;");
    htmlParts.push("      case 'delegate_plan': desc = '<b>' + (data.agent || '') + '</b> created its plan'; break;");
    htmlParts.push("      case 'tool_result': desc = '<b>' + (data.agent || '') + '</b> queried <i>' + (data.tool || '') + '</i> (' + (data.chars || 0) + ' chars)'; break;");
    htmlParts.push("      case 'delegate_done': desc = '<b>' + (data.agent || '') + '</b> finished (' + (data.chars || 0) + ' chars)'; break;");
    htmlParts.push("      case 'synthesizing': desc = '<b>' + (data.agent || '') + '</b> is synthesizing the final answer'; break;");
    htmlParts.push("      default: desc = JSON.stringify(data);");
    htmlParts.push('    }');
    htmlParts.push("    var detail = '';");
    htmlParts.push("    if ((data.type === 'planning' || data.type === 'delegate_plan') && data.content) { detail = data.content; }");
    htmlParts.push("    else if (data.type === 'delegate_start' && Array.isArray(data.tasks) && data.tasks.length) {");
    htmlParts.push("      detail = data.tasks.map(function(t, i) { return (i + 1) + '. ' + t; }).join('\\n');");
    htmlParts.push('    }');
    htmlParts.push("    else if (data.type === 'tool_result' && data.content) { detail = data.content; }");
    htmlParts.push("    var item = document.createElement('div');");
    htmlParts.push("    item.className = 'activity-item' + (detail ? ' expandable' : '');");
    htmlParts.push("    var bodyEl = document.createElement('span');");
    htmlParts.push("    bodyEl.className = 'activity-item-body';");
    htmlParts.push('    bodyEl.innerHTML = desc;');
    htmlParts.push('    if (detail) {');
    htmlParts.push("      var detailEl = document.createElement('div');");
    htmlParts.push("      detailEl.className = 'activity-detail';");
    htmlParts.push('      detailEl.textContent = detail;');
    htmlParts.push('      bodyEl.appendChild(detailEl);');
    htmlParts.push("      item.addEventListener('click', function() { item.classList.toggle('expanded'); });");
    htmlParts.push('    }');
    htmlParts.push("    item.innerHTML = '<span class=\"activity-item-icon\">' + icon + '</span>';");
    htmlParts.push('    item.appendChild(bodyEl);');
    htmlParts.push('    _activityItems.appendChild(item);');
    htmlParts.push('    _activityItems.scrollTop = _activityItems.scrollHeight;');
    htmlParts.push('    messagesEl.scrollTop = messagesEl.scrollHeight;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function collapseActivityPanel() {');
    htmlParts.push('    if (!_activityPanel) return;');
    htmlParts.push('    var elapsed = _activityStartTs ? Math.round((Date.now() - _activityStartTs) / 1000) : 0;');
    htmlParts.push("    var hdr = _activityPanel.querySelector('.activity-header span');");
    htmlParts.push("    if (hdr) hdr.textContent = 'Processed in ' + elapsed + 's \\u2014 click to expand';");
    htmlParts.push("    _activityPanel.classList.add('collapsed');");
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function resetActivityPanel() {');
    htmlParts.push('    _activityPanel = null; _activityItems = null; _activityHeader = null; _activityStartTs = null;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function showHumanInputModal(title, message) {');
    htmlParts.push("    humanInputTitle.textContent = title || 'Input Required';");
    htmlParts.push("    humanInputMessage.textContent = message || 'Please provide your input to continue.';");
    htmlParts.push("    humanInputTextarea.value = '';");
    htmlParts.push("    humanInputModal.classList.add('active');");
    htmlParts.push('    humanInputTextarea.focus();');
    htmlParts.push('    awaitingHumanInput = true;');
    htmlParts.push('    inputEl.disabled = true;');
    htmlParts.push('    sendBtn.disabled = true;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function hideHumanInputModal() {');
    htmlParts.push("    humanInputModal.classList.remove('active');");
    htmlParts.push('    awaitingHumanInput = false;');
    htmlParts.push('    inputEl.disabled = false;');
    htmlParts.push('    sendBtn.disabled = false;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  async function submitHumanInput() {');
    htmlParts.push('    const userInput = humanInputTextarea.value.trim();');
    htmlParts.push('    if (!userInput) { alert("Please enter your response"); return; }');
    htmlParts.push('    humanInputSubmit.disabled = true;');
    htmlParts.push("    statusEl.textContent = 'Submitting...';");
    htmlParts.push('    try {');
    htmlParts.push('      const resp = await fetch(SUBMIT_INPUT_URL, {');
    htmlParts.push("        method: 'POST',");
    htmlParts.push("        headers: { 'Content-Type': 'application/json' },");
    htmlParts.push('        body: JSON.stringify({ session_id: sessionId, user_input: userInput })');
    htmlParts.push('      });');
    htmlParts.push('      if (!resp.ok) { const err = await resp.json().catch(() => ({})); throw new Error(err.error || "HTTP " + resp.status); }');
    htmlParts.push('      const data = await resp.json();');
    htmlParts.push("      appendMessage('user', userInput);");
    htmlParts.push("      messages.push({ role: 'user', content: userInput });");
    htmlParts.push('      hideHumanInputModal();');
    htmlParts.push("      if (data.status === 'awaiting_human_input') {");
    htmlParts.push('        showHumanInputModal(data.title, data.last_conversation_message);');
    htmlParts.push('        currentExecutionId = data.execution_id;');
    htmlParts.push("      } else if (data.status === 'success') {");
    htmlParts.push("        const reply = data.response || '(No response)';");
    htmlParts.push("        appendMessage('assistant', reply, false, data.citations);");
    htmlParts.push("        messages.push({ role: 'assistant', content: reply });");
    htmlParts.push("        statusEl.textContent = '';");
    htmlParts.push('        currentExecutionId = null;');
    htmlParts.push("      } else if (data.status === 'processing') {");
    htmlParts.push("        statusEl.textContent = 'Processing...';");
    htmlParts.push("        setTimeout(() => { statusEl.textContent = ''; }, 2000);");
    htmlParts.push('      } else {');
    htmlParts.push("        appendMessage('assistant', 'Error: ' + (data.error || 'Unexpected error'));");
    htmlParts.push("        statusEl.textContent = '';");
    htmlParts.push('      }');
    htmlParts.push('    } catch (e) {');
    htmlParts.push("      console.error('Submit error:', e);");
    htmlParts.push("      appendMessage('assistant', 'Sorry, there was a problem.');");
    htmlParts.push("      statusEl.textContent = e.message || 'Error';");
    htmlParts.push('    } finally {');
    htmlParts.push('      humanInputSubmit.disabled = false;');
    htmlParts.push('    }');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  async function sendMessage() {');
    htmlParts.push('    const text = inputEl.value.trim();');
    htmlParts.push('    if (!text || awaitingHumanInput) return;');
    htmlParts.push("    appendMessage('user', text);");
    htmlParts.push("    messages.push({ role: 'user', content: text });");
    htmlParts.push("    inputEl.value = '';");
    htmlParts.push("    inputEl.style.height = 'auto';");
    htmlParts.push('    sendBtn.disabled = true;');
    htmlParts.push("    statusEl.textContent = '';");
    htmlParts.push('    showThinkingIndicator();');
    htmlParts.push('    try {');
    htmlParts.push('      const resp = await fetch(STREAM_URL, {');
    htmlParts.push("        method: 'POST',");
    htmlParts.push("        headers: { 'Content-Type': 'application/json' },");
    htmlParts.push('        body: JSON.stringify({ user_query: text, session_id: sessionId })');
    htmlParts.push('      });');
    htmlParts.push("      if (!resp.ok) throw new Error('HTTP ' + resp.status);");
    htmlParts.push('      let thinkingHidden = false;');
    htmlParts.push('      let msg = null, bubble = null, markdownEl = null;');
    htmlParts.push("      let accumulatedContent = '';");
    htmlParts.push('      const reader = resp.body.getReader();');
    htmlParts.push('      const decoder = new TextDecoder();');
    htmlParts.push('      while (true) {');
    htmlParts.push('        const { done, value } = await reader.read();');
    htmlParts.push('        if (done) break;');
    htmlParts.push('        const chunk = decoder.decode(value, { stream: true });');
    htmlParts.push("        const lines = chunk.split('\\n');");
    htmlParts.push('        for (const line of lines) {');
    htmlParts.push("          if (line.startsWith('data: ')) {");
    htmlParts.push('            try {');
    htmlParts.push('              const data = JSON.parse(line.slice(6));');
    htmlParts.push("              if (data.type === 'content') {");
    htmlParts.push('                if (!thinkingHidden) {');
    htmlParts.push('                  collapseActivityPanel();');
    htmlParts.push('                  hideThinkingIndicator();');
    htmlParts.push('                  thinkingHidden = true;');
    htmlParts.push("                  msg = document.createElement('div');");
    htmlParts.push("                  msg.className = 'msg assistant';");
    htmlParts.push("                  bubble = document.createElement('div');");
    htmlParts.push("                  bubble.className = 'bubble';");
    htmlParts.push("                  markdownEl = document.createElement('markdown');");
    htmlParts.push('                  bubble.appendChild(markdownEl);');
    htmlParts.push('                  msg.appendChild(bubble);');
    htmlParts.push('                  messagesEl.appendChild(msg);');
    htmlParts.push('                }');
    htmlParts.push('                accumulatedContent += data.content;');
    htmlParts.push('                markdownEl.innerHTML = renderMarkdown(accumulatedContent);');
    htmlParts.push('                messagesEl.scrollTop = messagesEl.scrollHeight;');
    htmlParts.push("              } else if (data.type === 'citations') {");
    htmlParts.push('                if (markdownEl && Array.isArray(data.citations) && data.citations.length > 0) {');
    htmlParts.push('                  _chatCitations = data.citations;');
    htmlParts.push('                  markdownEl.innerHTML = renderCitationChips(renderMarkdown(accumulatedContent), data.citations);');
    htmlParts.push('                  messagesEl.scrollTop = messagesEl.scrollHeight;');
    htmlParts.push('                }');
    htmlParts.push("              } else if (data.type === 'planning' || data.type === 'delegate_start' || data.type === 'delegate_plan' || data.type === 'tool_result' || data.type === 'delegate_done' || data.type === 'synthesizing') {");
    htmlParts.push('                showActivityItem(data);');
    htmlParts.push("              } else if (data.type === 'awaiting_human_input') {");
    htmlParts.push('                hideThinkingIndicator();');
    htmlParts.push('                showHumanInputModal(data.title, data.last_conversation_message);');
    htmlParts.push('                currentExecutionId = data.execution_id;');
    htmlParts.push("                statusEl.textContent = 'Waiting for input...';");
    htmlParts.push('                if (msg) msg.remove();');
    htmlParts.push('                return;');
    htmlParts.push("              } else if (data.type === 'error') {");
    htmlParts.push('                hideThinkingIndicator();');
    htmlParts.push('                if (msg) msg.remove();');
    htmlParts.push("                appendMessage('assistant', 'Error: ' + (data.error || 'Unexpected error'));");
    htmlParts.push('                return;');
    htmlParts.push("              } else if (data.type === 'done') {");
    htmlParts.push('                collapseActivityPanel();');
    htmlParts.push('                var parsed = parseCitations(accumulatedContent);');
    htmlParts.push('                var cleanContent = parsed.cleanText;');
    htmlParts.push('                var citations = [];');
    htmlParts.push('                if (Array.isArray(data.citations) && data.citations.length > 0) { citations = data.citations; }');
    htmlParts.push('                else if (_chatCitations.length > 0) { citations = _chatCitations; }');
    htmlParts.push('                else { citations = parsed.citations; }');
    htmlParts.push('                _chatCitations = citations;');
    htmlParts.push('                if (markdownEl) {');
    htmlParts.push('                  markdownEl.innerHTML = citations.length > 0 ? renderCitationChips(renderMarkdown(cleanContent), citations) : renderMarkdown(cleanContent);');
    htmlParts.push('                }');
    htmlParts.push("                messages.push({ role: 'assistant', content: cleanContent });");
    htmlParts.push("                statusEl.textContent = '';");
    htmlParts.push('                resetActivityPanel();');
    htmlParts.push('                return;');
    htmlParts.push('              }');
    htmlParts.push("            } catch (e) { console.error('Parse error:', e); }");
    htmlParts.push('          }');
    htmlParts.push('        }');
    htmlParts.push('      }');
    htmlParts.push('    } catch (e) {');
    htmlParts.push("      console.error('Chat error:', e);");
    htmlParts.push('      hideThinkingIndicator();');
    htmlParts.push('      collapseActivityPanel();');
    htmlParts.push('      resetActivityPanel();');
    htmlParts.push("      appendMessage('assistant', 'Sorry, there was a connection problem.');");
    htmlParts.push("      statusEl.textContent = '';");
    htmlParts.push('    } finally {');
    htmlParts.push('      if (!awaitingHumanInput) sendBtn.disabled = false;');
    htmlParts.push('    }');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push("  sendBtn.addEventListener('click', sendMessage);");
    htmlParts.push("  inputEl.addEventListener('keydown', (e) => {");
    htmlParts.push("    if (e.key === 'Enter' && !e.shiftKey && !awaitingHumanInput) {");
    htmlParts.push('      e.preventDefault();');
    htmlParts.push('      sendMessage();');
    htmlParts.push('    }');
    htmlParts.push('  });');
    htmlParts.push('');
    htmlParts.push("  humanInputSubmit.addEventListener('click', submitHumanInput);");
    htmlParts.push("  humanInputCancel.addEventListener('click', () => { hideHumanInputModal(); statusEl.textContent = ''; });");
    htmlParts.push("  humanInputTextarea.addEventListener('keydown', (e) => {");
    htmlParts.push("    if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); submitHumanInput(); }");
    htmlParts.push('  });');
    htmlParts.push('');
    htmlParts.push("  document.addEventListener('keydown', function(e) {");
    htmlParts.push("    if (e.key === 'Escape') { try { parent.postMessage({ type: 'chatbot_escape' }, '*'); } catch(_) {} }");
    htmlParts.push('  });');
    htmlParts.push('');
    htmlParts.push('</' + 'script>');
    htmlParts.push('</body>');
    htmlParts.push('</html>');
    
    return htmlParts.join('\n');
  }
  
  // Reactive variable that calls the function - track all branding dependencies
  $: embedCode = endpointUrl && initialGreeting ? generateEmbedCode() : '';
  // Trigger regeneration when branding settings change
  $: if (chatbotTitle || chatbotSubtitle || primaryColor || secondaryColor || logoUrl) {
    if (endpointUrl && initialGreeting) {
      embedCode = generateEmbedCode();
    }
  }
  
  onMount(() => {
    loadDeployment();
    loadWorkflows();
  });
  
  async function loadDeployment() {
    try {
      loading = true;
      console.log(`📋 DEPLOYMENT: Loading deployment for project ${projectId}`);
      
      const data = await cleanUniversalApi.getDeployment(projectId);
      
      deployment = data.deployment;
      workflows = data.available_workflows || [];
      allowedOrigins = data.allowed_origins || [];
      
      if (deployment) {
        selectedWorkflowId = deployment.workflow_id || '';
        isActive = deployment.is_active || false;
        rateLimitPerMinute = deployment.rate_limit_per_minute || 10;
        initialGreeting = deployment.initial_greeting || initialGreeting;
        
        // Load branding customization
        chatbotTitle = deployment.chatbot_title || 'AI Assistant';
        chatbotSubtitle = deployment.chatbot_subtitle || 'Powered by AICC IntelliDoc';
        primaryColor = deployment.primary_color || '#78b2e8';
        secondaryColor = deployment.secondary_color || '#3a6d98';
        logoUrl = deployment.logo_url || '';
        fileUploadsEnabled = deployment.file_uploads_enabled || false;

        // Construct endpoint URL
        const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';
        endpointUrl = `${baseUrl}${deployment.endpoint_path}`;
        
        // Debug logging
        console.log('🔗 DEPLOYMENT: endpointUrl =', endpointUrl);
        console.log('🔗 DEPLOYMENT: initialGreeting =', initialGreeting);
        console.log('🎨 DEPLOYMENT: Branding loaded - title:', chatbotTitle, 'colors:', primaryColor, secondaryColor);
      }
      
      console.log(`✅ DEPLOYMENT: Loaded deployment data`);
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to load deployment:', error);
      toasts.error('Failed to load deployment configuration');
    } finally {
      loading = false;
    }
  }
  
  async function loadWorkflows() {
    try {
      const auth = get(authStore);
      const token = auth?.token || '';
      
      const response = await fetch(`/api/projects/${projectId}/workflows/`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to load workflows: ${response.status}`);
      }
      
      const data = await response.json();
      workflows = Array.isArray(data) ? data : (data.workflows || data.results || []);
      
      // If no workflow selected and we have workflows, select first one
      if (workflows.length > 0 && !selectedWorkflowId) {
        selectedWorkflowId = workflows[0].workflow_id;
      }
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to load workflows:', error);
    }
  }
  
  async function saveDeployment() {
    if (!selectedWorkflowId) {
      toasts.error('Please select a workflow to deploy');
      return;
    }
    
    try {
      saving = true;
      console.log(`💾 DEPLOYMENT: Saving deployment configuration`);
      
      await cleanUniversalApi.updateDeployment(projectId, {
        workflow_id: selectedWorkflowId,
        rate_limit_per_minute: rateLimitPerMinute,
        initial_greeting: initialGreeting,
        // Branding customization
        chatbot_title: chatbotTitle,
        chatbot_subtitle: chatbotSubtitle,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
        logo_url: logoUrl || null,
        file_uploads_enabled: fileUploadsEnabled
      });
      
      toasts.success('Deployment configuration saved successfully');
      await loadDeployment();
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to save deployment:', error);
      toasts.error(error.message || 'Failed to save deployment configuration');
    } finally {
      saving = false;
    }
  }
  
  async function toggleDeployment() {
    try {
      saving = true;
      console.log(`🔄 DEPLOYMENT: Toggling deployment to ${!isActive ? 'active' : 'inactive'}`);
      
      const result = await cleanUniversalApi.toggleDeployment(projectId);
      isActive = result.is_active;
      
      toasts.success(result.message || `Deployment ${isActive ? 'activated' : 'deactivated'} successfully`);
      await loadDeployment();
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to toggle deployment:', error);
      toasts.error(error.message || 'Failed to toggle deployment');
    } finally {
      saving = false;
    }
  }
  
  async function addOrigin() {
    if (!newOrigin.trim()) {
      toasts.error('Please enter an origin URL');
      return;
    }
    
    // Basic validation
    if (!newOrigin.startsWith('http://') && !newOrigin.startsWith('https://')) {
      toasts.error('Origin must start with http:// or https://');
      return;
    }
    
    try {
      saving = true;
      console.log(`➕ DEPLOYMENT: Adding origin ${newOrigin}`);
      
      await cleanUniversalApi.addAllowedOrigin(projectId, {
        origin: newOrigin.trim(),
        rate_limit_per_minute: newOriginRateLimit
      });
      
      toasts.success('Origin added successfully');
      newOrigin = '';
      newOriginRateLimit = rateLimitPerMinute;
      showAddOrigin = false;
      await loadDeployment();
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to add origin:', error);
      toasts.error(error.message || 'Failed to add origin');
    } finally {
      saving = false;
    }
  }
  
  async function removeOrigin(originId: number) {
    if (!confirm('Are you sure you want to remove this origin?')) {
      return;
    }
    
    try {
      saving = true;
      console.log(`🗑️ DEPLOYMENT: Removing origin ${originId}`);
      
      await cleanUniversalApi.removeAllowedOrigin(projectId, originId);
      
      toasts.success('Origin removed successfully');
      await loadDeployment();
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to remove origin:', error);
      toasts.error(error.message || 'Failed to remove origin');
    } finally {
      saving = false;
    }
  }
  
  async function updateOrigin(origin: any) {
    try {
      saving = true;
      console.log(`🔄 DEPLOYMENT: Updating origin ${origin.id}`);
      
      await cleanUniversalApi.updateOriginRateLimit(projectId, origin.id, {
        rate_limit_per_minute: origin.rate_limit_per_minute,
        is_active: origin.is_active
      });
      
      toasts.success('Origin updated successfully');
      await loadDeployment();
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to update origin:', error);
      toasts.error(error.message || 'Failed to update origin');
    } finally {
      saving = false;
    }
  }
  
  function copyEndpointUrl() {
    if (typeof window !== 'undefined' && endpointUrl) {
      navigator.clipboard.writeText(endpointUrl);
      toasts.success('Endpoint URL copied to clipboard');
    }
  }
  
  function copyEmbedCode() {
    if (typeof navigator !== 'undefined' && navigator.clipboard && embedCode) {
      navigator.clipboard.writeText(embedCode);
      toasts.success('HTML embed code copied to clipboard');
    }
  }
</script>

<div class="workflow-deployment-container">
  <div class="deployment-header">
    <h2 class="text-2xl font-bold text-gray-900 mb-2">
      <i class="fas fa-rocket mr-2 text-oxford-blue"></i>
      Workflow Deployment
    </h2>
    <p class="text-gray-600 mb-6">Deploy your workflows as public-facing chatbots</p>
  </div>
  
  {#if loading}
    <div class="flex items-center justify-center min-h-96">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
        <p class="text-oxford-blue">Loading deployment configuration...</p>
      </div>
    </div>
  {:else}
    <!-- Deployment Status Section -->
    <div class="deployment-section mb-8">
      <h3 class="text-xl font-semibold text-gray-900 mb-4">
        <i class="fas fa-cog mr-2 text-oxford-blue"></i>
        Deployment Configuration
      </h3>
      
      <div class="bg-white rounded-lg shadow-md p-6">
        <!-- Workflow Selection -->
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Select Workflow to Deploy
          </label>
          <select
            bind:value={selectedWorkflowId}
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
            disabled={saving}
          >
            <option value="">-- Select a workflow --</option>
            {#each workflows as workflow}
              <option value={workflow.workflow_id}>
                {workflow.name} {workflow.description ? `- ${workflow.description}` : ''}
              </option>
            {/each}
          </select>
          {#if workflows.length === 0}
            <p class="text-sm text-gray-500 mt-2">
              <i class="fas fa-info-circle mr-1"></i>
              No workflows available. Create a workflow in the Agent Orchestration tab first.
            </p>
          {/if}
        </div>
        
        <!-- Rate Limit Setting -->
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Default Rate Limit (requests per minute)
          </label>
          <input
            type="number"
            bind:value={rateLimitPerMinute}
            min="1"
            max="1000"
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
            disabled={saving}
          />
          <p class="text-sm text-gray-500 mt-1">
            This is the default rate limit for origins without specific limits
          </p>
        </div>
        
        <!-- Save Button -->
        <button
          on:click={saveDeployment}
          disabled={saving || !selectedWorkflowId}
          class="px-6 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {#if saving}
            <i class="fas fa-spinner fa-spin mr-2"></i>
            Saving...
          {:else}
            <i class="fas fa-save mr-2"></i>
            Save Configuration
          {/if}
        </button>
      </div>
    </div>
    
    <!-- Deployment Status Toggle -->
    {#if deployment && deployment.workflow_id}
      <div class="deployment-section mb-8">
        <h3 class="text-xl font-semibold text-gray-900 mb-4">
          <i class="fas fa-power-off mr-2 text-oxford-blue"></i>
          Deployment Status
        </h3>
        
        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="flex items-center justify-between mb-4">
            <div>
              <p class="text-sm font-medium text-gray-700 mb-1">Deployment Status</p>
              <p class="text-lg font-semibold {isActive ? 'text-green-600' : 'text-gray-500'}">
                {isActive ? 'Active' : 'Inactive'}
              </p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                bind:checked={isActive}
                on:change={toggleDeployment}
                disabled={saving}
                class="sr-only peer"
              />
              <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-oxford-blue/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-oxford-blue"></div>
            </label>
          </div>
          
          <!-- Endpoint URL -->
          <div class="mt-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Endpoint URL
            </label>
            <div class="flex items-center gap-2">
              <input
                type="text"
                value={endpointUrl}
                readonly
                class="flex-1 px-4 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-700"
              />
              <button
                on:click={copyEndpointUrl}
                class="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
                title="Copy to clipboard"
              >
                <i class="fas fa-copy"></i>
              </button>
            </div>
            <p class="text-sm text-gray-500 mt-1">
              Use this endpoint to access your deployed workflow
            </p>
          </div>
        </div>
      </div>
    {/if}
    
    <!-- Allowed Origins Section -->
    <div class="deployment-section mb-8">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-xl font-semibold text-gray-900">
          <i class="fas fa-globe mr-2 text-oxford-blue"></i>
          Allowed Origins
        </h3>
        <button
          on:click={() => showAddOrigin = !showAddOrigin}
          class="px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors"
        >
          <i class="fas fa-plus mr-2"></i>
          Add Origin
        </button>
      </div>
      
      <!-- Add Origin Form -->
      {#if showAddOrigin}
        <div class="bg-white rounded-lg shadow-md p-6 mb-4">
          <h4 class="text-lg font-medium text-gray-900 mb-4">Add New Origin</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Origin URL
              </label>
              <input
                type="text"
                bind:value={newOrigin}
                placeholder="https://example.com"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Rate Limit (per minute)
              </label>
              <input
                type="number"
                bind:value={newOriginRateLimit}
                min="1"
                max="1000"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
              />
            </div>
          </div>
          <div class="flex gap-2">
            <button
              on:click={addOrigin}
              disabled={saving}
              class="px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors disabled:opacity-50"
            >
              <i class="fas fa-check mr-2"></i>
              Add
            </button>
            <button
              on:click={() => { showAddOrigin = false; newOrigin = ''; }}
              class="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      {/if}
      
      <!-- Origins List -->
      <div class="bg-white rounded-lg shadow-md overflow-hidden">
        {#if allowedOrigins.length === 0}
          <div class="p-8 text-center text-gray-500">
            <i class="fas fa-inbox text-4xl mb-4"></i>
            <p>No allowed origins configured</p>
            <p class="text-sm mt-2">Add origins to allow specific domains to access your deployed workflow</p>
          </div>
        {:else}
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Origin</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rate Limit</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              {#each allowedOrigins as origin}
                <tr>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm font-medium text-gray-900">{origin.origin}</div>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <input
                      type="number"
                      bind:value={origin.rate_limit_per_minute}
                      min="1"
                      max="1000"
                      on:blur={() => updateOrigin(origin)}
                      class="w-24 px-2 py-1 border border-gray-300 rounded text-sm"
                    />
                    <span class="text-xs text-gray-500 ml-1">/min</span>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <label class="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        bind:checked={origin.is_active}
                        on:change={() => updateOrigin(origin)}
                        class="sr-only peer"
                      />
                      <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-oxford-blue/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-oxford-blue"></div>
                      <span class="ml-2 text-sm text-gray-700">{origin.is_active ? 'Active' : 'Inactive'}</span>
                    </label>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      on:click={() => removeOrigin(origin.id)}
                      class="text-red-600 hover:text-red-900"
                    >
                      <i class="fas fa-trash"></i>
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    </div>
    
    <!-- Embed Code Section -->
    {#if deployment && deployment.workflow_id && endpointUrl}
      <div class="deployment-section mb-8">
        <h3 class="text-xl font-semibold text-gray-900 mb-4">
          <i class="fas fa-code mr-2 text-oxford-blue"></i>
          Embed Code
        </h3>
        
        <div class="bg-white rounded-lg shadow-md p-6 space-y-6">
          <!-- Greeting Editor -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Initial Greeting Message
            </label>
            <input
              type="text"
              bind:value={initialGreeting}
              class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
              placeholder="Hi! I am your AI assistant."
            />
            <p class="text-sm text-gray-500 mt-1">
              This message will be shown as the first assistant message in the embedded chatbot. Changes are project-specific.
            </p>
          </div>

          <!-- Embed Snippet -->
          <!-- Chatbot Branding Customization -->
          <div class="mt-8 pt-6 border-t border-gray-200">
            <h4 class="text-lg font-semibold text-gray-900 mb-4">
              <i class="fas fa-palette mr-2 text-oxford-blue"></i>
              Chatbot Branding
            </h4>
            <p class="text-sm text-gray-600 mb-6">
              Customize the appearance of your embedded chatbot to match your brand.
            </p>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <!-- Chatbot Title -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Chatbot Title
                </label>
                <input
                  type="text"
                  bind:value={chatbotTitle}
                  class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
                  placeholder="AI Assistant"
                />
              </div>
              
              <!-- Chatbot Subtitle -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Chatbot Subtitle
                </label>
                <input
                  type="text"
                  bind:value={chatbotSubtitle}
                  class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
                  placeholder="Powered by AICC IntelliDoc"
                />
              </div>
              
              <!-- Primary Color -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Primary Color
                </label>
                <div class="flex items-center gap-3">
                  <input
                    type="color"
                    bind:value={primaryColor}
                    class="w-12 h-10 border border-gray-300 rounded-md cursor-pointer p-1"
                  />
                  <input
                    type="text"
                    bind:value={primaryColor}
                    class="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue font-mono text-sm"
                    placeholder="#0b3b66"
                    maxlength="7"
                  />
                </div>
                <p class="text-xs text-gray-500 mt-1">Header background and user message bubbles</p>
              </div>
              
              <!-- Secondary Color -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Secondary Color (Gradient)
                </label>
                <div class="flex items-center gap-3">
                  <input
                    type="color"
                    bind:value={secondaryColor}
                    class="w-12 h-10 border border-gray-300 rounded-md cursor-pointer p-1"
                  />
                  <input
                    type="text"
                    bind:value={secondaryColor}
                    class="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue font-mono text-sm"
                    placeholder="#1e5a8a"
                    maxlength="7"
                  />
                </div>
                <p class="text-xs text-gray-500 mt-1">Used for gradient effects</p>
              </div>
            </div>
            
            <!-- Logo URL -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Logo URL (Optional)
              </label>
              <input
                type="url"
                bind:value={logoUrl}
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
                placeholder="https://example.com/logo.png"
              />
              <p class="text-xs text-gray-500 mt-1">
                URL to your logo image. Leave empty to display the first letter of the title. Recommended size: 44x44px or larger.
              </p>
            </div>
            
            <!-- File Uploads Toggle -->
            <div class="mb-6">
              <label class="flex items-center gap-3 cursor-pointer">
                <div class="relative">
                  <input
                    type="checkbox"
                    bind:checked={fileUploadsEnabled}
                    class="sr-only peer"
                  />
                  <div class="w-10 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-oxford-blue"></div>
                </div>
                <div>
                  <span class="text-sm font-medium text-gray-700">Allow File Uploads</span>
                  <p class="text-xs text-gray-500">
                    {fileUploadsEnabled ? 'Users can attach PDF, TXT, DOC, DOCX, MD, RTF files in the chatbot' : 'File upload is disabled for chatbot users'}
                  </p>
                </div>
              </label>
            </div>

            <!-- Live Preview -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Header Preview
              </label>
              <div 
                class="rounded-xl overflow-hidden shadow-lg"
                style="max-width: 420px;"
              >
                <div 
                  class="flex items-center gap-3 p-4 text-white"
                  style="background: linear-gradient(135deg, {primaryColor} 0%, {secondaryColor} 100%);"
                >
                  <div 
                    class="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                    style="background: rgba(255, 255, 255, 0.2);"
                  >
                    {#if logoUrl}
                      <img src={logoUrl} alt="Logo" class="w-full h-full object-cover rounded-xl" />
                    {:else}
                      <span class="text-lg font-bold text-white uppercase">
                        {chatbotTitle ? chatbotTitle[0] : 'A'}
                      </span>
                    {/if}
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="font-bold text-base truncate">{chatbotTitle || 'AI Assistant'}</div>
                    <div class="text-xs opacity-85 truncate">{chatbotSubtitle || 'Powered by AICC IntelliDoc'}</div>
                  </div>
                  <div class="w-2.5 h-2.5 bg-green-400 rounded-full shadow-[0_0_0_3px_rgba(34,197,94,0.3)]"></div>
                </div>
              </div>
            </div>
            
            <!-- Save Branding Button -->
            <button
              on:click={saveDeployment}
              disabled={saving || !selectedWorkflowId}
              class="px-6 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {#if saving}
                <i class="fas fa-spinner fa-spin mr-2"></i>
                Saving...
              {:else}
                <i class="fas fa-save mr-2"></i>
                Save Branding
              {/if}
            </button>
          </div>

          <!-- Embed Snippet -->
          <div class="mt-8 pt-6 border-t border-gray-200">
            <div class="flex items-center justify-between mb-2">
              <label class="block text-sm font-medium text-gray-700">
                HTML Embed Code (copy and paste into your website)
              </label>
              <button
                on:click={copyEmbedCode}
                class="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-xs font-medium"
              >
                <i class="fas fa-copy mr-1"></i>
                Copy
              </button>
            </div>
            <textarea
              readonly
              class="w-full h-72 font-mono text-xs px-3 py-3 border border-gray-300 rounded-md bg-gray-50 text-gray-800"
            >{embedCode}</textarea>
            <p class="text-sm text-gray-500 mt-2">
              <i class="fas fa-info-circle mr-1"></i>
              Copy and paste this HTML code into your website where you want the chatbot to appear. The chatbot will load automatically.
            </p>
          </div>
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .workflow-deployment-container {
    @apply p-6 max-w-6xl mx-auto;
  }
  
  .deployment-section {
    @apply mb-8;
  }
</style>

