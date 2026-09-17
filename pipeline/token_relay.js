#!/usr/bin/env node
/**
 * token_relay.js — tar emot GitHub-token från webbläsaren (POST localhost:5299/token),
 * bygger dashboard-länken med token i #-delen och skickar den till Marcs Telegram.
 * Claude ser aldrig nyckeln: den går webbläsare → denna process → Telegram, och
 * dessutom öppnas länken i Marcs standardwebbläsare på datorn så att den sparas där.
 *
 * Sidan (docs/approvals.js) läser #gh=<token>, sparar i localStorage och tar bort
 * den ur adressfältet. Fragmentet (#...) skickas aldrig till någon server.
 *
 *   node token_relay.js            lyssnar tills en token kommit (max 10 min), avslutar sedan
 */
'use strict';
const http = require('http');
const os = require('os');
const path = require('path');
const { execFile } = require('child_process');
const lib = require(path.join(os.homedir(), '.claude', 'hooks', 'telegram-lib.js'));

const PORT = 5299;
const DASH = 'https://marcdshark666.github.io/drjonsson/';

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'content-type');
  if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }
  if (req.method !== 'POST' || req.url !== '/token') { res.writeHead(404); return res.end(); }
  let body = '';
  req.on('data', (c) => { body += c; if (body.length > 4096) req.destroy(); });
  req.on('end', async () => {
    const token = body.trim();
    if (!/^(github_pat_|ghp_)[A-Za-z0-9_]{20,}$/.test(token)) { res.writeHead(400); res.end('bad token'); return; }
    res.writeHead(200); res.end('ok');
    const link = DASH + '#gh=' + encodeURIComponent(token);
    try {
      const cfg = lib.loadConfig();
      await lib.sendMessage(cfg,
        '🔑 <b>DrJonsson-dashboarden</b>\nÖppna länken EN gång på mobilen så sparas din GitHub-nyckel i den webbläsaren, ' +
        'och ✅/❌/Redigera/Radera fungerar utan att fråga:\n' + lib.escapeHtml(link) +
        '\n\nNyckeln kan bara skriva i repot drjonsson. Radera gärna det här meddelandet efteråt.');
      console.log('telegram: skickat');
    } catch (e) {
      console.error('telegram misslyckades: ' + e.message);
    }
    // Oppna aven pa datorn (Marcs standardwebblasare) sa att den sparas dar.
    execFile('cmd.exe', ['/c', 'start', '', link], { windowsHide: true }, () => {});
    setTimeout(() => process.exit(0), 1500);
  });
});
server.listen(PORT, '127.0.0.1', () => console.log('relay lyssnar på 127.0.0.1:' + PORT));
setTimeout(() => { console.log('timeout, ingen token'); process.exit(2); }, 10 * 60 * 1000);
