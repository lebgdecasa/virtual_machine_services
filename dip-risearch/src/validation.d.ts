import { z } from 'zod';
export declare const ResearchRequestSchema: z.ZodObject<{
    query: z.ZodString;
    depth: z.ZodDefault<z.ZodNumber>;
    breadth: z.ZodDefault<z.ZodNumber>;
    model: z.ZodOptional<z.ZodEnum<["o3-mini", "deepseek-r1", "gemini-flash"]>>;
}, "strip", z.ZodTypeAny, {
    query: string;
    breadth: number;
    depth: number;
    model?: "o3-mini" | "deepseek-r1" | "gemini-flash" | undefined;
}, {
    query: string;
    model?: "o3-mini" | "deepseek-r1" | "gemini-flash" | undefined;
    breadth?: number | undefined;
    depth?: number | undefined;
}>;
export declare const ReportRequestSchema: z.ZodObject<{
    query: z.ZodString;
    depth: z.ZodDefault<z.ZodNumber>;
    breadth: z.ZodDefault<z.ZodNumber>;
    model: z.ZodOptional<z.ZodEnum<["o3-mini", "deepseek-r1", "gemini-flash"]>>;
}, "strip", z.ZodTypeAny, {
    query: string;
    breadth: number;
    depth: number;
    model?: "o3-mini" | "deepseek-r1" | "gemini-flash" | undefined;
}, {
    query: string;
    model?: "o3-mini" | "deepseek-r1" | "gemini-flash" | undefined;
    breadth?: number | undefined;
    depth?: number | undefined;
}>;
export declare const HealthResponseSchema: z.ZodObject<{
    status: z.ZodString;
    timestamp: z.ZodString;
    uptime: z.ZodNumber;
    version: z.ZodString;
    memory: z.ZodObject<{
        used: z.ZodNumber;
        total: z.ZodNumber;
        free: z.ZodNumber;
    }, "strip", z.ZodTypeAny, {
        used: number;
        total: number;
        free: number;
    }, {
        used: number;
        total: number;
        free: number;
    }>;
}, "strip", z.ZodTypeAny, {
    status: string;
    timestamp: string;
    uptime: number;
    version: string;
    memory: {
        used: number;
        total: number;
        free: number;
    };
}, {
    status: string;
    timestamp: string;
    uptime: number;
    version: string;
    memory: {
        used: number;
        total: number;
        free: number;
    };
}>;
export declare const ErrorResponseSchema: z.ZodObject<{
    error: z.ZodString;
    message: z.ZodString;
    code: z.ZodOptional<z.ZodString>;
    details: z.ZodOptional<z.ZodAny>;
}, "strip", z.ZodTypeAny, {
    message: string;
    error: string;
    code?: string | undefined;
    details?: any;
}, {
    message: string;
    error: string;
    code?: string | undefined;
    details?: any;
}>;
export type ResearchRequest = z.infer<typeof ResearchRequestSchema>;
export type ReportRequest = z.infer<typeof ReportRequestSchema>;
export type HealthResponse = z.infer<typeof HealthResponseSchema>;
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;
//# sourceMappingURL=validation.d.ts.map