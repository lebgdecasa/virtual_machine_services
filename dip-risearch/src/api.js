import cors from 'cors';
import express from 'express';
import { z } from 'zod';
import { deepResearch, writeFinalReport } from './deep-research';
import { logger } from './logger';
import { globalRateLimiter, researchRateLimiter } from './rate-limiter';
import { ResearchRequestSchema, ReportRequestSchema, HealthResponseSchema } from './validation';
const app = express();
const port = process.env.PORT || 8080;
// Trust proxy for accurate IP addresses (important for rate limiting)
app.set('trust proxy', 1);
// Security middleware
app.use((req, res, next) => {
    // Remove X-Powered-By header
    res.removeHeader('X-Powered-By');
    // Security headers
    res.set({
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
    });
    next();
});
// CORS configuration
const corsOptions = {
    origin: (origin, callback) => {
        const allowedOrigins = process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'];
        if (!origin || allowedOrigins.includes(origin) || process.env.NODE_ENV === 'development') {
            callback(null, true);
        }
        else {
            callback(new Error('Not allowed by CORS'));
        }
    },
    credentials: true,
    methods: ['GET', 'POST', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With'],
};
app.use(cors(corsOptions));
// Body parsing middleware with size limits
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
// Request logging middleware
app.use(async (req, res, next) => {
    const start = Date.now();
    res.on('finish', async () => {
        const duration = Date.now() - start;
        await logger.logRequest(req, res, duration);
    });
    next();
});
// Global rate limiting
app.use(globalRateLimiter.middleware());
// Health check endpoint
app.get('/health', async (req, res) => {
    try {
        const uptime = process.uptime();
        const memUsage = process.memoryUsage();
        const healthData = {
            status: 'healthy',
            timestamp: new Date().toISOString(),
            uptime: Math.floor(uptime),
            version: process.env.npm_package_version || '1.0.0',
            memory: {
                used: Math.floor(memUsage.used / 1024 / 1024), // MB
                total: Math.floor(memUsage.total / 1024 / 1024), // MB
                free: Math.floor((memUsage.total - memUsage.used) / 1024 / 1024), // MB
            },
        };
        // Validate response
        HealthResponseSchema.parse(healthData);
        res.json(healthData);
    }
    catch (error) {
        logger.error('Health check failed', error);
        res.status(500).json({ status: 'unhealthy', error: 'Health check failed' });
    }
});
// Error handling middleware
app.use((error, req, res, next) => {
    if (error instanceof z.ZodError) {
        const errorResponse = {
            error: 'Validation Error',
            message: 'Invalid request data',
            code: 'VALIDATION_ERROR',
            details: error.errors,
        };
        return res.status(400).json(errorResponse);
    }
    if (error.message === 'Not allowed by CORS') {
        const errorResponse = {
            error: 'CORS Error',
            message: 'Origin not allowed',
            code: 'CORS_ERROR',
        };
        return res.status(403).json(errorResponse);
    }
    logger.error('Unhandled error', error, { url: req.url, method: req.method });
    res.status(500).json({
        error: 'Internal Server Error',
        message: 'An unexpected error occurred',
    });
});
// API endpoint to run research
app.post('/api/research', researchRateLimiter.middleware(), async (req, res) => {
    try {
        // Validate request body
        const validatedData = ResearchRequestSchema.parse(req.body);
        const { query, depth, breadth, model } = validatedData;
        await logger.info('Starting research request', {
            query: query.substring(0, 100), // Log first 100 chars for privacy
            depth,
            breadth,
            model,
            ip: req.ip,
        });
        // Set timeout for research operation
        const timeoutMs = Number(process.env.RESEARCH_TIMEOUT) || 300000; // 5 minutes default
        const timeoutPromise = new Promise((_, reject) => setTimeout(() => reject(new Error('Research operation timed out')), timeoutMs));
        const researchPromise = deepResearch({
            query,
            breadth,
            depth,
        });
        const { learnings, visitedUrls } = await Promise.race([researchPromise, timeoutPromise]);
        await logger.info('Research completed', {
            learningsCount: learnings?.length || 0,
            urlsCount: visitedUrls?.length || 0,
        });
        const reportPromise = writeFinalReport({
            prompt: query,
            learnings: learnings || [],
            visitedUrls: visitedUrls || [],
        });
        const reportTimeoutPromise = new Promise((_, reject) => setTimeout(() => reject(new Error('Report generation timed out')), 60000) // 1 minute
        );
        const answer = await Promise.race([reportPromise, reportTimeoutPromise]);
        // Return the results
        return res.json({
            success: true,
            answer,
            learnings: learnings || [],
            visitedUrls: visitedUrls || [],
            metadata: {
                queryLength: query.length,
                learningsCount: learnings?.length || 0,
                urlsCount: visitedUrls?.length || 0,
                processingTime: Date.now() - Date.now(), // Would need to track actual time
            },
        });
    }
    catch (error) {
        await logger.error('Research API error', error, {
            url: req.url,
            method: req.method,
            ip: req.ip,
            body: req.body,
        });
        if (error.name === 'ZodError') {
            const errorResponse = {
                error: 'Validation Error',
                message: 'Invalid request parameters',
                code: 'VALIDATION_ERROR',
                details: error.errors,
            };
            return res.status(400).json(errorResponse);
        }
        if (error.message.includes('timed out')) {
            const errorResponse = {
                error: 'Timeout Error',
                message: 'Research operation exceeded time limit',
                code: 'TIMEOUT_ERROR',
            };
            return res.status(408).json(errorResponse);
        }
        const errorResponse = {
            error: 'Research Error',
            message: error.message || 'An error occurred during research',
            code: 'RESEARCH_ERROR',
        };
        return res.status(500).json(errorResponse);
    }
});
// Generate report API (deprecated - use /api/research instead)
app.post('/api/generate-report', researchRateLimiter.middleware(), async (req, res) => {
    try {
        // Validate request body
        const validatedData = ReportRequestSchema.parse(req.body);
        const { query, depth, breadth } = validatedData;
        await logger.warn('Using deprecated /api/generate-report endpoint', {
            query: query.substring(0, 100),
            depth,
            breadth,
            ip: req.ip,
        });
        // Set timeout for research operation
        const timeoutMs = Number(process.env.RESEARCH_TIMEOUT) || 300000; // 5 minutes default
        const timeoutPromise = new Promise((_, reject) => setTimeout(() => reject(new Error('Research operation timed out')), timeoutMs));
        const researchPromise = deepResearch({
            query,
            breadth,
            depth,
        });
        const { learnings, visitedUrls } = await Promise.race([researchPromise, timeoutPromise]);
        const reportPromise = writeFinalReport({
            prompt: query,
            learnings: learnings || [],
            visitedUrls: visitedUrls || [],
        });
        const reportTimeoutPromise = new Promise((_, reject) => setTimeout(() => reject(new Error('Report generation timed out')), 60000) // 1 minute
        );
        const report = await Promise.race([reportPromise, reportTimeoutPromise]);
        // Return the report as plain text (legacy format)
        res.setHeader('Content-Type', 'text/plain; charset=utf-8');
        return res.send(report);
    }
    catch (error) {
        await logger.error('Generate report API error', error, {
            url: req.url,
            method: req.method,
            ip: req.ip,
            body: req.body,
        });
        if (error.name === 'ZodError') {
            const errorResponse = {
                error: 'Validation Error',
                message: 'Invalid request parameters',
                code: 'VALIDATION_ERROR',
                details: error.errors,
            };
            return res.status(400).json(errorResponse);
        }
        if (error.message.includes('timed out')) {
            const errorResponse = {
                error: 'Timeout Error',
                message: 'Research operation exceeded time limit',
                code: 'TIMEOUT_ERROR',
            };
            return res.status(408).json(errorResponse);
        }
        const errorResponse = {
            error: 'Research Error',
            message: error.message || 'An error occurred during research',
            code: 'RESEARCH_ERROR',
        };
        return res.status(500).json(errorResponse);
    }
});
// Graceful shutdown handling
const server = app.listen(port, () => {
    logger.info(`Deep Research API running on port ${port}`, {
        nodeEnv: process.env.NODE_ENV,
        port,
    });
});
// Handle graceful shutdown
const gracefulShutdown = async (signal) => {
    await logger.info(`Received ${signal}, starting graceful shutdown...`);
    server.close(async () => {
        await logger.info('HTTP server closed');
        // Close any other resources here if needed
        process.exit(0);
    });
    // Force close server after 10 seconds
    setTimeout(async () => {
        await logger.error('Could not close connections in time, forcefully shutting down');
        process.exit(1);
    }, 10000);
};
// Handle different termination signals
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
process.on('SIGUSR2', () => gracefulShutdown('SIGUSR2')); // nodemon restart
// Handle uncaught exceptions and unhandled rejections
process.on('uncaughtException', async (error) => {
    await logger.error('Uncaught Exception', error);
    process.exit(1);
});
process.on('unhandledRejection', async (reason, promise) => {
    await logger.error('Unhandled Rejection at', new Error(reason?.toString() || 'Unknown'), {
        promise: promise.toString(),
    });
    process.exit(1);
});
export default app;
