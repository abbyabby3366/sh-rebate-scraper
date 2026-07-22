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

let statusInfo = {
  last_run: null,
  last_status: 'Ready',
  is_running: false,
  run_count: 0
};

function executePythonScraper() {
  if (statusInfo.is_running) {
    console.log('Scraper is already running. Skipping duplicate trigger.');
    return;
  }

  statusInfo.is_running = true;
  statusInfo.last_status = 'Running...';
  console.log(`[${new Date().toISOString()}] Starting python main.py scraper...`);

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
      statusInfo.last_run = new Date().toLocaleString();
      statusInfo.run_count += 1;
      console.log('Python scraper completed successfully.');
    } else {
      statusInfo.last_status = `Failed with exit code ${code}`;
      console.error(`Python scraper exited with code ${code}`);
    }
  });
}

// Schedule cron every 6 hours
cron.schedule('0 */6 * * *', () => {
  console.log('Triggering 6-hour scheduled rebate scrape...');
  executePythonScraper();
});

// Health check endpoint for Render
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'healthy', timestamp: new Date() });
});

// Status API
app.get('/api/status', (req, res) => {
  res.json({
    service: 'Winbox/SH Rebate Scraper Express Server',
    status: 'Online',
    scraper_info: statusInfo,
    schedule: 'Every 6 hours'
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
  console.log(`Express server listening on 0.0.0.0:${PORT}`);
});
