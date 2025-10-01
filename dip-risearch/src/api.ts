import cors from 'cors';
import express, { Request, Response } from 'express';

import { deepResearch, writeFinalAnswer,writeFinalReport } from './deep-research';

const app = express();
const port = process.env.PORT || 8080;

// Middleware
app.use(cors());
app.use(express.json());

// Enhanced logging function for debugging
function log(level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG', message: string, data?: any) {
  const timestamp = new Date().toISOString();
  const prefix = `[${timestamp}] [${level}] [API]`;

  if (data !== undefined) {
    console.log(`${prefix} ${message}`, data);
  } else {
    console.log(`${prefix} ${message}`);
  }
}

// Convenience logging functions
function logInfo(message: string, data?: any) {
  log('INFO', message, data);
}

function logWarn(message: string, data?: any) {
  log('WARN', message, data);
}

function logError(message: string, error?: any) {
  log('ERROR', message, error);
}

function logDebug(message: string, data?: any) {
  log('DEBUG', message, data);
}

// API endpoint to run research
app.post('/api/research', async (req: Request, res: Response) => {
  const requestStartTime = Date.now();
  const requestId = Math.random().toString(36).substring(7);

  try {
    logInfo(`[${requestId}] Research request received`, {
      method: req.method,
      path: req.path,
      ip: req.ip,
      userAgent: req.get('User-Agent')?.slice(0, 100)
    });

    const { query, depth = 3, breadth = 3 } = req.body;

    logDebug(`[${requestId}] Request body`, { query, depth, breadth });

    if (!query) {
      logWarn(`[${requestId}] Missing query parameter`, { query, depth, breadth });
      return res.status(400).json({ error: 'Query is required' });
    }

    logInfo(`[${requestId}] Starting research`, { query, depth, breadth });

    const researchStartTime = Date.now();
    const { learnings, visitedUrls } = await deepResearch({
      query,
      breadth,
      depth,
    });
    const researchDuration = Date.now() - researchStartTime;

    logInfo(`[${requestId}] Research completed`, {
      duration: `${researchDuration}ms`,
      learningsCount: learnings.length,
      urlsCount: visitedUrls.length
    });

    logDebug(`[${requestId}] Research results`, {
      learnings: learnings.slice(0, 3), // Log first 3 learnings as preview
      urlsCount: visitedUrls.length,
      sampleUrls: visitedUrls.slice(0, 3)
    });

    const reportStartTime = Date.now();
    const answer = await writeFinalReport({
      prompt: query,
      learnings,
      visitedUrls
    });
    const reportDuration = Date.now() - reportStartTime;

    logInfo(`[${requestId}] Report generated`, {
      reportDuration: `${reportDuration}ms`,
      reportLength: answer.length
    });

    const totalDuration = Date.now() - requestStartTime;

    logInfo(`[${requestId}] Request completed successfully`, {
      totalDuration: `${totalDuration}ms`,
      statusCode: 200
    });

    // Return the results
    return res.json({
      success: true,
      answer,
      learnings,
      visitedUrls,
    });
  } catch (error: unknown) {
    const totalDuration = Date.now() - requestStartTime;

    logError(`[${requestId}] Request failed`, {
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
      totalDuration: `${totalDuration}ms`
    });

    return res.status(500).json({
      error: 'An error occurred during research',
      message: error instanceof Error ? error.message : String(error),
    });
  }
});

// generate report API
app.post('/api/generate-report', async (req: Request, res: Response) => {
  const requestStartTime = Date.now();
  const requestId = Math.random().toString(36).substring(7);

  try {
    logInfo(`[${requestId}] Generate report request received`, {
      method: req.method,
      path: req.path,
      ip: req.ip,
      userAgent: req.get('User-Agent')?.slice(0, 100)
    });

    const { query, depth = 3, breadth = 3 } = req.body;

    logDebug(`[${requestId}] Request body`, { query, depth, breadth });

    if (!query) {
      logWarn(`[${requestId}] Missing query parameter`, { query, depth, breadth });
      return res.status(400).json({ error: 'Query is required' });
    }

    logInfo(`[${requestId}] Starting research for report`, { query, depth, breadth });

    const researchStartTime = Date.now();
    const { learnings, visitedUrls } = await deepResearch({
      query,
      breadth,
      depth
    });
    const researchDuration = Date.now() - researchStartTime;

    logInfo(`[${requestId}] Research completed for report`, {
      duration: `${researchDuration}ms`,
      learningsCount: learnings.length,
      urlsCount: visitedUrls.length
    });

    logDebug(`[${requestId}] Research results for report`, {
      learnings: learnings.slice(0, 3), // Log first 3 learnings as preview
      urlsCount: visitedUrls.length,
      sampleUrls: visitedUrls.slice(0, 3)
    });

    const reportStartTime = Date.now();
    const report = await writeFinalReport({
      prompt: query,
      learnings,
      visitedUrls
    });
    const reportDuration = Date.now() - reportStartTime;

    logInfo(`[${requestId}] Report generated successfully`, {
      reportDuration: `${reportDuration}ms`,
      reportLength: report.length
    });

    const totalDuration = Date.now() - requestStartTime;

    logInfo(`[${requestId}] Generate report request completed`, {
      totalDuration: `${totalDuration}ms`,
      statusCode: 200
    });

    return res.json({
      success: true,
      report,
      learnings,
      visitedUrls,
    });

  } catch (error: unknown) {
    const totalDuration = Date.now() - requestStartTime;

    logError(`[${requestId}] Generate report request failed`, {
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
      totalDuration: `${totalDuration}ms`
    });

    return res.status(500).json({
      error: 'An error occurred during research',
      message: error instanceof Error ? error.message : String(error),
    });
  }
});



// Start the server
app.listen(port, () => {
  logInfo('Deep Research API server started', {
    port,
    environment: process.env.NODE_ENV || 'development',
    concurrencyLimit: process.env.CUSTOM_API_CONCURRENCY || '2',
    apiBaseUrl: process.env.CUSTOM_API_BASE_URL || 'http://34.30.168.182'
  });
});

export default app;
