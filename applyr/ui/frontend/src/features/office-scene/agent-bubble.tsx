import { Container, Graphics, Text, Sprite } from "pixi.js";
import type { AgentVisualState, WorkArtifact } from "./types";
import { VISUAL_PROPS, ARTIFACT_ICONS } from "./types";

/** Bubble offset above agent head (y is up in Pixi) */
const BUBBLE_OFFSET_Y = -80;

/** Bubble dimensions */
const BUBBLE_WIDTH = 220;
const BUBBLE_HEIGHT = 100;
const BUBBLE_PADDING = 12;
const BUBBLE_RADIUS = 8;
const BUBBLE_TAIL_HEIGHT = 16;
const BUBBLE_TAIL_WIDTH = 20;

/** Font sizes */
const FONT_SIZE_STATE = 11;
const FONT_SIZE_TASK = 10;
const FONT_SIZE_COMMAND = 9;
const FONT_SIZE_OUTPUT = 9;

/** Animation durations */
const BUBBLE_APPEAR_DURATION = 0.15;
const BUBBLE_DISAPPEAR_DURATION = 0.1;

export interface AgentBubbleContent {
  state: AgentVisualState;
  task?: string;
  command?: string;
  outputSummary?: string;
  artifact?: WorkArtifact;
}

/** Result of bubble creation for external control */
export interface AgentBubbleHandle {
  view: Container;
  setContent: (content: AgentBubbleContent) => void;
  show: () => void;
  hide: () => void;
  destroy: () => void;
  isVisible: () => boolean;
}

/**
 * Creates a speech/work bubble for an agent.
 * The bubble shows:
 * - Current state (icon + label)
 * - Current task (1 line)
 * - Current command if running (1 line, monospace)
 * - Output summary (1 line, truncated)
 * - Artifact icon if carrying one
 * 
 * Clicking the bubble emits a 'bubble:click' event with the agentId
 * for the Inspector to handle.
 */
export function createAgentBubble(
  agentId: string,
  initialContent: AgentBubbleContent
): AgentBubbleHandle {
  const view = new Container();
  view.y = BUBBLE_OFFSET_Y;
  view.visible = true;
  view.eventMode = "static";
  view.cursor = "pointer";

  // Bubble background
  const bg = new Graphics();
  view.addChild(bg);

  // State icon + label
  const stateText = new Text({
    text: "",
    style: {
      fontSize: FONT_SIZE_STATE,
      fill: 0xf0ede6,
      fontWeight: "600",
      fontFamily: "Inter Variable, ui-sans-serif, system-ui",
    },
  });
  stateText.anchor.set(0, 0);
  view.addChild(stateText);

  // Task text
  const taskText = new Text({
    text: "",
    style: {
      fontSize: FONT_SIZE_TASK,
      fill: 0xf0ede6,
      fontFamily: "Inter Variable, ui-sans-serif, system-ui",
      wordWrap: true,
      wordWrapWidth: BUBBLE_WIDTH - 2 * BUBBLE_PADDING,
    },
  });
  taskText.anchor.set(0, 0);
  view.addChild(taskText);

  // Command text (monospace)
  const commandText = new Text({
    text: "",
    style: {
      fontSize: FONT_SIZE_COMMAND,
      fill: 0x9b9488,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas",
      wordWrap: true,
      wordWrapWidth: BUBBLE_WIDTH - 2 * BUBBLE_PADDING,
    },
  });
  commandText.anchor.set(0, 0);
  view.addChild(commandText);

  // Output summary
  const outputText = new Text({
    text: "",
    style: {
      fontSize: FONT_SIZE_OUTPUT,
      fill: 0x4fa98a,
      fontFamily: "Inter Variable, ui-sans-serif, system-ui",
      wordWrap: true,
      wordWrapWidth: BUBBLE_WIDTH - 2 * BUBBLE_PADDING,
    },
  });
  outputText.anchor.set(0, 0);
  view.addChild(outputText);

  // Artifact indicator
  const artifactText = new Text({
    text: "",
    style: {
      fontSize: FONT_SIZE_TASK,
      fill: 0xf59e0b,
      fontFamily: "Inter Variable, ui-sans-serif, system-ui",
      fontWeight: "600",
    },
  });
  artifactText.anchor.set(0, 0);
  artifactText.visible = false;
  view.addChild(artifactText);

  let isVisible = true;
  let currentContent = initialContent;

  // Click handler for Inspector
  view.on("pointerdown", () => {
    view.emit("bubble:click", { agentId, content: currentContent });
  });

  // Also listen for pointerup to prevent click-through issues
  view.on("pointerup", () => {});

  const paintBubble = () => {
    bg.clear();
    
    const bubbleY = 0;
    const tailY = BUBBLE_HEIGHT;
    
    // Bubble background with tail pointing down to agent
    bg.roundRect(
      0,
      bubbleY,
      BUBBLE_WIDTH,
      BUBBLE_HEIGHT,
      BUBBLE_RADIUS
    );
    
    // Tail
    const centerX = BUBBLE_WIDTH / 2;
    bg.moveTo(centerX - BUBBLE_TAIL_WIDTH / 2, tailY);
    bg.lineTo(centerX, tailY + BUBBLE_TAIL_HEIGHT);
    bg.lineTo(centerX + BUBBLE_TAIL_WIDTH / 2, tailY);
    bg.closePath();
    
    bg.fill({ color: 0x1a1917, alpha: 0.95 });
    bg.stroke({ color: 0x33302b, width: 1, alpha: 0.8 });
  };

  const layoutText = () => {
    let y = BUBBLE_PADDING;
    const x = BUBBLE_PADDING;
    const maxWidth = BUBBLE_WIDTH - 2 * BUBBLE_PADDING;
    const props = VISUAL_PROPS[currentContent.state];

    // State line: icon + label
    stateText.text = `${props.icon} ${props.label}`;
    stateText.x = x;
    stateText.y = y;
    y += FONT_SIZE_STATE + 6;

    // Task
    if (currentContent.task) {
      taskText.text = currentContent.task;
      taskText.x = x;
      taskText.y = y;
      taskText.visible = true;
      y += Math.min(taskText.height, FONT_SIZE_TASK * 2) + 4;
    } else {
      taskText.visible = false;
    }

    // Command
    if (currentContent.command) {
      commandText.text = `$ ${currentContent.command}`;
      commandText.x = x;
      commandText.y = y;
      commandText.visible = true;
      y += FONT_SIZE_COMMAND + 4;
    } else {
      commandText.visible = false;
    }

    // Output summary
    if (currentContent.outputSummary) {
      const summary = currentContent.outputSummary.length > 80
        ? currentContent.outputSummary.slice(0, 77) + "..."
        : currentContent.outputSummary;
      outputText.text = summary;
      outputText.x = x;
      outputText.y = y;
      outputText.visible = true;
      y += Math.min(outputText.height, FONT_SIZE_OUTPUT * 2) + 4;
    } else {
      outputText.visible = false;
    }

    // Artifact
    if (currentContent.artifact) {
      artifactText.text = `${ARTIFACT_ICONS[currentContent.artifact.type]} ${currentContent.artifact.type.replace("_", " ")}`;
      artifactText.x = x;
      artifactText.y = y;
      artifactText.visible = true;
    } else {
      artifactText.visible = false;
    }
  };

  const setContent = (content: AgentBubbleContent) => {
    currentContent = content;
    layoutText();
    paintBubble();
  };

  const show = () => {
    if (isVisible) return;
    isVisible = true;
    view.visible = true;
    view.alpha = 0;
    view.scale.set(0.8);
    gsap.to(view, {
      alpha: 1,
      scale: 1,
      duration: BUBBLE_APPEAR_DURATION,
      ease: "back.out(1.5)",
    });
  };

  const hide = () => {
    if (!isVisible) return;
    isVisible = false;
    gsap.to(view, {
      alpha: 0,
      scale: 0.8,
      duration: BUBBLE_DISAPPEAR_DURATION,
      ease: "power2.in",
      onComplete: () => {
        view.visible = false;
      },
    });
  };

  const isVisibleFn = () => isVisible;

  const destroy = () => {
    gsap.killTweensOf(view);
    view.destroy({ children: true });
  };

  // Initial paint
  paintBubble();
  layoutText();

  return {
    view,
    setContent,
    show,
    hide,
    destroy,
    isVisible: isVisibleFn,
  };
}