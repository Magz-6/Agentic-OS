/**
 * AgenticOS v0.1 Alpha - Request Handler (Mock Engine)
 * 
 * ARCHITECTURAL DESIGN:
 * This module is strictly decoupled from the UI. It simulates the core pipeline
 * of the AgenticOS execution kernel:
 *   1. Intent Parsing & Validation
 *   2. Security Policy & Permission Evaluation
 *   3. Simulated Execution (with mock telemetry and logs)
 *   4. Error State handling
 * 
 * When connecting to a real AgenticOS backend in future versions,
 * this file will be replaced or mapped to an HTTP/WebSocket client
 * without requiring any UI modifications.
 */

export class MockAgenticEngine {
  constructor() {
    this.pendingConfirmations = new Map();
  }

  /**
   * Determine whether a prompt indicates a destructive or sensitive operation.
   * NOTE: In this Alpha prototype, all responses are strictly simulated.
   */
  classifyRisk(promptText) {
    const text = promptText.toLowerCase().trim();

    // Check for explicit error simulation trigger
    if (
      text.includes('error') ||
      text.includes('fail') ||
      text.includes('crash') ||
      text.includes('simulate error') ||
      text.includes('bug')
    ) {
      return {
        type: 'ERROR_SIMULATION',
        riskLevel: 'LOW',
        requiresConfirmation: false,
        reason: 'User explicitly requested an error state simulation.'
      };
    }

    // Check for destructive or high-risk actions
    const destructivePatterns = [
      { pattern: /\b(format|partition|wipe|erase|purge)\b/i, label: 'Storage / Data Purge' },
      { pattern: /\b(rm\s+-rf|del\s+\/s|remove-item\s+-recurse)\b/i, label: 'Recursive Deletion' },
      { pattern: /\b(drop\s+database|drop\s+table|truncate)\b/i, label: 'Database Drop' },
      { pattern: /\b(kill|terminate|shutdown|reboot)\s+(kernel|os|system|core|all)\b/i, label: 'System Process Termination' },
      { pattern: /\b(chmod\s+777|disable\s+firewall|override\s+security)\b/i, label: 'Security Override' }
    ];

    for (const dp of destructivePatterns) {
      if (dp.pattern.test(text)) {
        return {
          type: 'DESTRUCTIVE_ACTION',
          riskLevel: 'HIGH',
          requiresConfirmation: true,
          actionLabel: dp.label,
          targetResource: this.extractTargetResource(text),
          warning: 'This action has the potential to permanently alter or destroy system assets or data. Manual operator confirmation is required by AgenticOS Policy Kernel v0.1.'
        };
      }
    }

    // Standard safe operational tasks
    return {
      type: 'STANDARD_TASK',
      riskLevel: 'SAFE',
      requiresConfirmation: false,
      reason: 'Standard read/write or analysis intent verified within sandbox bounds.'
    };
  }

  extractTargetResource(text) {
    if (text.includes('/dev/') || text.includes('drive') || text.includes('partition')) {
      const match = text.match(/(\/dev\/[a-z0-9]+|[a-zA-Z]:\\[^\s]*)/i);
      return match ? match[0] : 'Storage Volume [Primary Partition]';
    }
    if (text.includes('database') || text.includes('table')) {
      return 'Relational Database Engine';
    }
    if (text.includes('core') || text.includes('kernel')) {
      return 'AgenticOS Kernel Core Services';
    }
    return 'Protected System Resource';
  }

  /**
   * Main request execution entry point.
   * Calls onProgress callback at each phase to update the UI pipeline.
   */
  async executePrompt(promptText, onProgress = () => {}) {
    const trimmedPrompt = promptText.trim();
    if (!trimmedPrompt) {
      throw new Error('Prompt cannot be empty.');
    }

    // --- PHASE 1: INTENT PARSING & VALIDATION ---
    onProgress({
      phase: 'INTENT_VALIDATION',
      status: 'IN_PROGRESS',
      message: 'Parsing natural language semantics and extracting execution graph...'
    });
    await this.delay(450);

    const riskEvaluation = this.classifyRisk(trimmedPrompt);

    onProgress({
      phase: 'INTENT_VALIDATION',
      status: 'COMPLETED',
      message: `Intent categorized: [${riskEvaluation.type}]. Parsed 1 execution node.`
    });
    await this.delay(350);

    // --- PHASE 2: SECURITY POLICY & PERMISSION CHECK ---
    onProgress({
      phase: 'PERMISSION_CHECK',
      status: 'IN_PROGRESS',
      message: `Auditing action against AgenticOS Security Sandbox (Risk: ${riskEvaluation.riskLevel})...`
    });
    await this.delay(500);

    // If an error state was specifically requested or simulated
    if (riskEvaluation.type === 'ERROR_SIMULATION') {
      onProgress({
        phase: 'PERMISSION_CHECK',
        status: 'FAILED',
        message: 'Security subsystem simulated a core dispatch exception.'
      });
      await this.delay(300);

      const simError = new Error('SIMULATED EXCEPTION: Neural Dispatcher Core encountered an unhandled fault (Error Code: A-OS-5003).');
      simError.code = 'ERR_SIMULATED_CORE_FAULT';
      simError.details = {
        subsystem: 'Kernel Dispatcher / Subagent Coordinator',
        vector: 'Simulated User Trigger',
        recovery: 'Reset workspace or execute a safe query to restore idle state.'
      };
      throw simError;
    }

    // If destructive action, halt and request human confirmation
    if (riskEvaluation.requiresConfirmation) {
      const actionId = 'act_' + Math.random().toString(36).substring(2, 9);
      this.pendingConfirmations.set(actionId, {
        prompt: trimmedPrompt,
        evaluation: riskEvaluation,
        timestamp: new Date().toISOString()
      });

      onProgress({
        phase: 'PERMISSION_CHECK',
        status: 'NEEDS_CONFIRMATION',
        message: `High-risk action flagged: [${riskEvaluation.actionLabel}]. User authorization mandated.`
      });

      return {
        status: 'AWAITING_CONFIRMATION',
        actionId,
        actionLabel: riskEvaluation.actionLabel,
        targetResource: riskEvaluation.targetResource,
        warning: riskEvaluation.warning,
        prompt: trimmedPrompt
      };
    }

    // Permission granted
    onProgress({
      phase: 'PERMISSION_CHECK',
      status: 'COMPLETED',
      message: 'Permissions verified: [SANDBOX_READ_WRITE_ALLOWED]. Proceeding to execution.'
    });
    await this.delay(400);

    // --- PHASE 3: SIMULATED AGENT EXECUTION ---
    onProgress({
      phase: 'AGENT_EXECUTION',
      status: 'IN_PROGRESS',
      message: 'Spawning simulated subagent worker in ephemeral sandbox...'
    });
    await this.delay(650);

    onProgress({
      phase: 'AGENT_EXECUTION',
      status: 'IN_PROGRESS',
      message: 'Running mock task routines and aggregating telemetry...'
    });
    await this.delay(500);

    onProgress({
      phase: 'AGENT_EXECUTION',
      status: 'COMPLETED',
      message: 'Mock execution finished with exit code 0.'
    });
    await this.delay(300);

    // --- PHASE 4: RESULT SYNTHESIS ---
    onProgress({
      phase: 'RESULT_SYNTHESIS',
      status: 'COMPLETED',
      message: 'Assembled response payload and execution telemetry.'
    });

    return this.generateMockResponse(trimmedPrompt, riskEvaluation);
  }

  /**
   * Resumes execution after user confirms a sensitive/destructive action.
   */
  async confirmAction(actionId, onProgress = () => {}) {
    const pending = this.pendingConfirmations.get(actionId);
    if (!pending) {
      throw new Error(`Confirmation token expired or invalid: ${actionId}`);
    }
    this.pendingConfirmations.delete(actionId);

    onProgress({
      phase: 'PERMISSION_CHECK',
      status: 'COMPLETED',
      message: 'Manual operator confirmation acknowledged. Security override granted for mock simulation.'
    });
    await this.delay(400);

    onProgress({
      phase: 'AGENT_EXECUTION',
      status: 'IN_PROGRESS',
      message: `Executing simulated sensitive action: ${pending.evaluation.actionLabel}...`
    });
    await this.delay(700);

    onProgress({
      phase: 'AGENT_EXECUTION',
      status: 'COMPLETED',
      message: 'Simulated operation completed safely without touching real host files or hardware.'
    });
    await this.delay(300);

    onProgress({
      phase: 'RESULT_SYNTHESIS',
      status: 'COMPLETED',
      message: 'Operation logged to AgenticOS mock audit trail.'
    });

    return {
      status: 'SUCCESS',
      isDestructiveSimulated: true,
      prompt: pending.prompt,
      actionLabel: pending.evaluation.actionLabel,
      targetResource: pending.evaluation.targetResource,
      responseText: `[SIMULATED EXECUTION COMPLETED]\n\nAction: "${pending.evaluation.actionLabel}" on target "${pending.evaluation.targetResource}".\n\nNotice: This was a strictly simulated operation inside the AgenticOS UI prototype. No actual host system files, partitions, or databases were modified or erased.`,
      auditLog: [
        `[AUDIT] Action token ${actionId} generated`,
        `[AUDIT] Risk level: HIGH`,
        `[AUDIT] Operator manual override confirmed`,
        `[AUDIT] Mock subagent executed in sandboxed dummy environment`,
        `[AUDIT] Zero real system modifications performed`
      ],
      metrics: {
        latencyMs: 1420,
        subagentsInvoked: 1,
        sandboxIntegrity: 'UNCOMPROMISED'
      }
    };
  }

  /**
   * Cancels a pending sensitive action.
   */
  cancelAction(actionId) {
    if (this.pendingConfirmations.has(actionId)) {
      this.pendingConfirmations.delete(actionId);
      return {
        status: 'CANCELLED',
        message: 'Sensitive action was successfully aborted by operator. No changes were simulated.'
      };
    }
    return { status: 'CANCELLED', message: 'Action cancelled.' };
  }

  /**
   * Generates rich mock response payloads for normal prompt executions.
   */
  generateMockResponse(prompt, riskEvaluation) {
    const text = prompt.toLowerCase();
    let responseText = '';
    let mockArtifacts = [];
    let logSteps = [
      'Initialized agent container [ctx: local-sandbox]',
      'Evaluated semantic context and constraints',
      'Compiled plan with 3 discrete task phases',
      'Synthesized output payload'
    ];

    if (text.includes('status') || text.includes('system') || text.includes('inspect')) {
      responseText = `### AgenticOS v0.1 Alpha Telemetry Report\n\n` +
        `* **Kernel Status:** Online & Nominal\n` +
        `* **Active Subagents:** 3 idle / 1 coordinating\n` +
        `* **Memory Allocation:** 142 MB virtual sandboxed heap\n` +
        `* **Sandbox State:** Isolated (No host filesystem access)\n` +
        `* **Security Kernel:** Strict Enforced v0.1\n\n` +
        `All subsystems are currently operating within prototype parameters.`;
      mockArtifacts.push({
        type: 'telemetry_json',
        title: 'telemetry_snapshot.json',
        data: { kernel: 'v0.1-alpha', uptime: '00:42:19', loadAvg: 0.14 }
      });
    } else if (text.includes('workflow') || text.includes('optimize') || text.includes('agent')) {
      responseText = `### AgenticOS Workflow Optimization\n\n` +
        `Analyzed current subagent communication graph:\n\n` +
        `1. **Telemetry Pipeline:** Streamlined message queue routing (reduced simulated dispatch latency by ~18%).\n` +
        `2. **Permission Checking:** Cached recent token approvals for read-only query streams.\n` +
        `3. **Memory Management:** Auto-reclaiming terminated subagent task contexts.\n\n` +
        `Ready to deploy optimized pipeline to simulation workers.`;
    } else {
      responseText = `### AgenticOS Response\n\n` +
        `Received prompt: *"${prompt}"*\n\n` +
        `The AgenticOS Alpha mock engine parsed your request, completed semantic validation, verified security policies, and synthesized this simulated response.\n\n` +
        `> **Note:** Once the real backend is connected, this request will be dispatched to live agent workers according to your permission policies.`;
    }

    return {
      status: 'SUCCESS',
      prompt,
      riskLevel: riskEvaluation.riskLevel,
      responseText,
      artifacts: mockArtifacts,
      auditLog: logSteps,
      metrics: {
        latencyMs: 1240,
        subagentsInvoked: 2,
        tokensSimulated: 184
      }
    };
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
