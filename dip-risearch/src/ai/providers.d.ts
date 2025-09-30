import { LanguageModel } from 'ai';
type FlexibleLanguageModel = LanguageModel | any;
export declare function getModel(): FlexibleLanguageModel;
export declare function clearModelCache(): void;
export declare function trimPrompt(prompt: string, contextSize?: number): string;
export {};
//# sourceMappingURL=providers.d.ts.map