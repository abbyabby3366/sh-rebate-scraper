const express = require('express');
const cron = require('node-cron');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 10000;

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// Set default timezone process env
process.env.TZ = 'Asia/Kuala_Lumpur';

let statusInfo = {
  last_run: null,
  last_status: 'Ready',
  is_running: false,
  run_count: 0
};

function formatMYTime(dateObj = new Date()) {
  return dateObj.toLocaleString('en-MY', {
    timeZone: 'Asia/Kuala_Lumpur',
    dateStyle: 'medium',
    timeStyle: 'medium'
  });
}

// Calculate next fixed daily scheduled time: 00:00, 06:00, 12:00, 18:00 GMT+8
function getNextFixedScheduledTime() {
  const now = new Date();
  const options = { timeZone: 'Asia/Kuala_Lumpur', hour12: false };
  const formatter = new Intl.DateTimeFormat('en-US', {
    ...options,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    second: 'numeric'
  });

  const parts = formatter.formatToParts(now);
  const getPart = type => parseInt(parts.find(p => p.type === type).value);

  const year = getPart('year');
  const month = getPart('month'); // 1-indexed
  const day = getPart('day');
  const currentHour = getPart('hour');

  const scheduledHours = [0, 6, 12, 18];
  let nextHour = scheduledHours.find(h => h > currentHour);

  let targetDateObj = new Date(now);

  if (nextHour === undefined) {
    // Tomorrow at 00:00
    nextHour = 0;
    // Add 1 day
    targetDateObj.setDate(targetDateObj.getDate() + 1);
  }

  // Format YYYY-MM-DD
  const tParts = formatter.formatToParts(targetDateObj);
  const tYear = tParts.find(p => p.type === 'year').value;
  const tMonth = tParts.find(p => p.type === 'month').value.padStart(2, '0');
  const tDay = tParts.find(p => p.type === 'day').value.padStart(2, '0');
  const padHour = String(nextHour).padStart(2, '0');

  // ISO string for Asia/Kuala_Lumpur (+08:00)
  const targetIsoStr = `${tYear}-${tMonth}-${tDay}T${padHour}:00:00+08:00`;
  return new Date(targetIsoStr);
}

function executePythonScraper() {
  if (statusInfo.is_running) {
    console.log('Scraper is already running. Skipping duplicate trigger.');
    return;
  }

  statusInfo.is_running = true;
  statusInfo.last_status = 'Running...';
  console.log(`[${formatMYTime()}] Starting python main.py scraper...`);

  const pyProcess = spawn('python', ['main.py']);

  pyProcess.stdout.on('data', (data) => {
    console.log(`[Scraper]: ${data.toString().trim()}`);
  });

  pyProcess.stderr.on('data', (data) => {
    console.error(`[Scraper Error]: ${data.toString().trim()}`);
  });

  pyProcess.on('close', (code) => {
    statusInfo.is_running = false;
    if (code === 0) {
      statusInfo.last_status = 'Success';
      statusInfo.last_run = formatMYTime();
      statusInfo.run_count += 1;
      console.log('Python scraper completed successfully.');
    } else {
      statusInfo.last_status = `Failed with exit code ${code}`;
      console.error(`Python scraper exited with code ${code}`);
    }
  });
}

// Schedule cron at fixed daily hours: 00:00, 06:00, 12:00, 18:00 (GMT+8 Malaysia Time)
cron.schedule('0 0,6,12,18 * * *', () => {
  console.log(`[${formatMYTime()}] Triggering fixed 6-hour scheduled rebate scrape (00:00 / 06:00 / 12:00 / 18:00 GMT+8)...`);
  executePythonScraper();
}, {
  scheduled: true,
  timezone: 'Asia/Kuala_Lumpur'
});

// Health check endpoint for Render
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'healthy', timestamp: formatMYTime(), timezone: 'GMT+8 (Asia/Kuala_Lumpur)' });
});

// Status API
app.get('/api/status', (req, res) => {
  const nextTarget = getNextFixedScheduledTime();
  res.json({
    service: 'Winbox/SH Rebate Scraper Express Server',
    status: 'Online',
    timezone: 'GMT+8 (Asia/Kuala_Lumpur)',
    scraper_info: statusInfo,
    next_run_timestamp: nextTarget.getTime(),
    next_run_formatted: formatMYTime(nextTarget),
    fixed_schedule: '00:00, 06:00, 12:00, 18:00 (GMT+8)'
  });
});

// Data API
app.get('/api/data', (req, res) => {
  const filePath = path.join(__dirname, 'commission_list.json');
  if (fs.existsSync(filePath)) {
    try {
      const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
      return res.json(data);
    } catch (e) {
      return res.status(500).json({ error: 'Failed to read data file' });
    }
  }
  res.json([]);
});

// Manual Trigger API
app.all('/api/trigger', (req, res) => {
  if (statusInfo.is_running) {
    return res.status(400).json({ status: 'error', message: 'Scraper is already running!' });
  }

  executePythonScraper();
  res.json({ status: 'success', message: 'Scraping job started in background!' });
});

// Serve Dashboard UI
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Express server listening on 0.0.0.0:${PORT} in GMT+8 (Asia/Kuala_Lumpur) timezone.`);
  console.log(`Fixed Daily Schedule: 00:00 | 06:00 | 12:00 | 18:00 (GMT+8)`);
});
