import { z } from 'zod';
// Research request validation
export const ResearchRequestSchema = z.object({
    query: z.string()
        .min(1, 'Query cannot be empty')
        .max(5000, 'Query too long (max 5000 characters)')
        .trim(),
    depth: z.number()
        .int('Depth must be an integer')
        .min(1, 'Depth must be at least 1')
        .max(10, 'Depth cannot exceed 10')
        .default(3),
    breadth: z.number()
        .int('Breadth must be an integer')
        .min(1, 'Breadth must be at least 1')
        .max(20, 'Breadth cannot exceed 20')
        .default(3),
    // Optional model override
    model: z.enum(['o3-mini', 'deepseek-r1', 'gemini-flash']).optional(),
});
// Generate report request validation (same as research but for report endpoint)
export const ReportRequestSchema = ResearchRequestSchema;
// Health check response
export const HealthResponseSchema = z.object({
    status: z.string(),
    timestamp: z.string(),
    uptime: z.number(),
    version: z.string(),
    memory: z.object({
        used: z.number(),
        total: z.number(),
        free: z.number(),
    }),
});
// Error response schema
export const ErrorResponseSchema = z.object({
    error: z.string(),
    message: z.string(),
    code: z.string().optional(),
    details: z.any().optional(),
});
