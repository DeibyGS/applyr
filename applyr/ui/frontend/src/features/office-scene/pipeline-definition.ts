/**
 * Pipeline Definition Loader — loads pipeline config from applyr.toml
 * with fallback to DEFAULT_PIPELINE.
 * Pure TypeScript, no React/Pixi dependencies.
 */

import type { PipelineDefinition, PipelineStage } from "./types";
import { DEFAULT_PIPELINE, validatePipeline } from "./types";

// TOML parsing is done on the backend; frontend receives JSON via API
// This file provides the TypeScript types and validation for the frontend

export interface PipelineStageConfig {
  id: string;
  name: string;
  position: { x: number; y: number };
  inputs: string[];
  outputs: string[];
  next_stages: string[];
}

export interface PipelineConfig {
  id: string;
  name: string;
  stages: PipelineStageConfig[];
}

/**
 * Convert backend pipeline config to frontend PipelineDefinition
 */
export function parsePipelineConfig(config: PipelineConfig): PipelineDefinition {
  const stages: PipelineStage[] = config.stages.map((s) => ({
    id: s.id as PipelineStage["id"],
    name: s.name,
    position: s.position,
    inputs: s.inputs as PipelineStage["inputs"],
    outputs: s.outputs as PipelineStage["outputs"],
    next_stages: s.next_stages as PipelineStage["next_stages"],
  }));

  return {
    id: config.id,
    name: config.name,
    stages,
  };
}

/**
 * Validate pipeline config and return errors (if any)
 */
export function validatePipelineConfig(config: PipelineConfig): string[] {
  const pipeline = parsePipelineConfig(config);
  return validatePipeline(pipeline);
}

/**
 * Get default pipeline (used when no config in applyr.toml)
 */
export function getDefaultPipeline(): PipelineDefinition {
  return DEFAULT_PIPELINE;
}

/**
 * Merge user config with defaults (user config takes precedence)
 */
export function mergePipelineConfig(
  userConfig: Partial<PipelineConfig> | null | undefined
): PipelineDefinition {
  if (!userConfig) {
    return DEFAULT_PIPELINE;
  }

  // Start with default
  const merged: PipelineConfig = {
    id: userConfig.id ?? DEFAULT_PIPELINE.id,
    name: userConfig.name ?? DEFAULT_PIPELINE.name,
    stages: DEFAULT_PIPELINE.stages.map((s) => ({
      id: s.id,
      name: s.name,
      position: s.position,
      inputs: s.inputs,
      outputs: s.outputs,
      next_stages: s.next_stages,
    })),
  };

  // Override with user stages
  if (userConfig.stages && userConfig.stages.length > 0) {
    const userStagesById = new Map(userConfig.stages.map((s) => [s.id, s]));

    merged.stages = merged.stages.map((defaultStage) => {
      const userStage = userStagesById.get(defaultStage.id);
      if (!userStage) return defaultStage;

      return {
        ...defaultStage,
        name: userStage.name ?? defaultStage.name,
        position: userStage.position ?? defaultStage.position,
        inputs: userStage.inputs.length > 0 ? userStage.inputs : defaultStage.inputs,
        outputs: userStage.outputs.length > 0 ? userStage.outputs : defaultStage.outputs,
        next_stages: userStage.next_stages.length > 0 ? userStage.next_stages : defaultStage.next_stages,
      };
    });

    // Add any entirely new stages from user config
    for (const userStage of userConfig.stages) {
      if (!merged.stages.some((s) => s.id === userStage.id)) {
        merged.stages.push({
          id: userStage.id,
          name: userStage.name,
          position: userStage.position ?? { x: 0, y: 0 },
          inputs: userStage.inputs,
          outputs: userStage.outputs,
          next_stages: userStage.next_stages,
        });
      }
    }
  }

  const errors = validatePipelineConfig(merged);
  if (errors.length > 0) {
    console.warn("[PipelineDefinition] Config validation warnings:", errors);
  }

  return parsePipelineConfig(merged);
}

/**
 * Backend API response type for pipeline config
 */
export interface PipelineConfigResponse {
  pipeline: PipelineConfig;
}

/**
 * Fetch pipeline config from backend
 */
export async function fetchPipelineConfig(baseUrl = ""): Promise<PipelineDefinition> {
  try {
    const response = await fetch(`${baseUrl}/api/pipeline-config`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = (await response.json()) as PipelineConfigResponse;
    return mergePipelineConfig(data.pipeline);
  } catch (error) {
    console.warn("[PipelineDefinition] Failed to fetch pipeline config, using default:", error);
    return DEFAULT_PIPELINE;
  }
}