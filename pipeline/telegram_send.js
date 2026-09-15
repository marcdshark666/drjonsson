#!/usr/bin/env node
/**
 * telegram_send.js — skickar text (och ev. en bild) till Marcs Telegram via
 * den gemensamma telegram-lib.js i ~/.claude/hooks. Ingen egen token här.
 *
 *   node telegram_send.js --text "Klart" [--bild kontaktark.jpg]
 */
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

const HOOKS = path.join(os.homedir(), '.claude', 'hooks');
const lib = require(path.join(HOOKS, 'telegram-lib.js'));

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : null;
}

async function sendPhoto(cfg, bildPath, caption) {
  const form = new FormData();
  form.append('chat_id', String(cfg.chatId));
  form.append('photo', new Blob([fs.readFileSync(bildPath)], { type: 'image/jpeg' }), path.basename(bildPath));
  if (caption) {
    form.append('caption', caption.slice(0, 1000));
    form.append('parse_mode', 'HTML');
  }
  const res = await fetch(`https://api.telegram.org/bot${cfg.botToken}/sendPhoto`, { method: 'POST', body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.description || `HTTP ${res.status}`);
  return data.result;
}

(async () => {
  const text = arg('--text') || '';
  const bild = arg('--bild');
  const cfg = lib.loadConfig();
  if (!cfg.botToken || !cfg.chatId) throw new Error('Telegram saknar token/chatId');
  const html = lib.escapeHtml(text);
  if (bild && fs.existsSync(bild)) {
    await sendPhoto(cfg, bild, html);
  } else {
    await lib.sendMessage(cfg, html);
  }
  console.log('skickat');
})().catch((e) => {
  console.error('telegram_send: ' + e.message);
  process.exit(1);
});
