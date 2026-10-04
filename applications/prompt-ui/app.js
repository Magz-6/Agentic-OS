/**
 * AgenticOS v0.1 Alpha - Application Controller (UI Presentation Layer)
 * 
 * Manages DOM events, animations, pipeline visualizations, modal dialogs,
 * and passes user requests to the decoupled MockAgenticEngine.
 */

import { MockAgenticEngine } from './request-handler.js';

class AgenticOSApp {
  constructor() {
    this.engine = new MockAgenticEngine();
    this.activeActionId = null;
    this.isProcessing = false;

    this.cacheDom();
    this.bindEvents();
    this.resetPipelineUI();
  }

  cacheDom() {
    // Inputs & Action triggers
    this.promptInput = document.getElementById('promptInput');
    this.executeBtn = document.getElementById('executeBtn');
    this.clearBtn = document.getElementById('clearBtn');
    this.presetChips = document.querySelectorAll('.preset-chip');

    // Pipeline Steps
    this.pipelineGlobalStatus = document.getElementById('pipelineGlobalStatus');
    this.tickerMessage = document.getElementById('tickerMessage');
    
    this.steps = {
      INTENT_VALIDATION: {
        el: document.getElementById('step-intent'),
        stateEl: document.getElementById('step-intent-state'),
        descEl: document.getElementById('step-intent-desc'),
        defaultDesc: 'Analyzes semantic intent and decomposes prompt into task graph.'
      },
      PERMISSION_CHECK: {
        el: document.getElementById('step-perm'),
        stateEl: document.getElementById('step-perm-state'),
        descEl: document.getElementById('step-perm-desc'),
        defaultDesc: 'Validates against AgenticOS safety policies and flags destructive operations.'
      },
      AGENT_EXECUTION: {
        el: document.getElementById('step-exec'),
        stateEl: document.getElementById('step-exec-state'),
        descEl: document.getElementById('step-exec-desc'),
        defaultDesc: 'Runs mock subagent workers inside isolated sandbox.'
      },
      RESULT_SYNTHESIS: {
        el: document.getElementById('step-result'),
        stateEl: document.getElementById('step-result-state'),
        descEl: document.getElementById('step-result-desc'),
        defaultDesc: 'Aggregates response, telemetry, and audit artifacts.'
      }
    };

    // Result & Error Views
    this.resultDisplay = document.getElementById('resultDisplay');
    this.metaLatency = document.getElementById('metaLatency');
    this.metaRisk = document.getElementById('metaRisk');
    
    this.errorBanner = document.getElementById('errorBanner');
    this.errorCode = document.getElementById('errorCode');
    this.errorMessage = document.getElementById('errorMessage');
    this.errSubsystem = document.getElementById('errSubsystem');
    this.errVector = document.getElementById('errVector');
    this.errRecovery = document.getElementById('errRecovery');
    this.dismissErrorBtn = document.getElementById('dismissErrorBtn');

    // Confirmation Modal Elements
    this.confirmOverlay = document.getElementById('confirmOverlay');
    this.modalActionName = document.getElementById('modalActionName');
    this.modalTargetResource = document.getElementById('modalTargetResource');
    this.modalWarningText = document.getElementById('modalWarningText');
    this.modalConfirmBtn = document.getElementById('modalConfirmBtn');
    this.modalCancelBtn = document.getElementById('modalCancelBtn');
  }

  bindEvents() {
    // Execute Button
    this.executeBtn.addEventListener('click', () => this.handleExecute());

    // Clear Button
    this.clearBtn.addEventListener('click', () => {
      this.promptInput.value = '';
      this.promptInput.focus();
    });

    // Preset Chips
    this.presetChips.forEach(chip => {
      chip.addEventListener('click', () => {
        const presetText = chip.getAttribute('data-preset');
        this.promptInput.value = presetText;
        this.promptInput.focus();
        this.handleExecute();
      });
    });

    // Keyboard Shortcuts
    this.promptInput.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        this.handleExecute();
      }
    });

    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && (this.isModalVisible() || this.activeActionId)) {
        e.preventDefault();
        this.handleCancelConfirmation();
      }
    });

    // Confirmation Modal Actions
    this.modalConfirmBtn.addEventListener('click', (e) => {
      e.preventDefault();
      this.handleConfirmAction();
    });

    this.modalCancelBtn.addEventListener('click', (e) => {
      e.preventDefault();
      this.handleCancelConfirmation();
    });

    // Clicking the backdrop outside modal card also cancels
    this.confirmOverlay.addEventListener('click', (e) => {
      if (e.target === this.confirmOverlay) {
        this.handleCancelConfirmation();
      }
    });

    // Dismiss Error
    this.dismissErrorBtn.addEventListener('click', () => {
      this.hideErrorBanner();
      this.resetPipelineUI();
    });
  }

  resetPipelineUI() {
    this.pipelineGlobalStatus.className = 'status-badge badge-idle';
    this.pipelineGlobalStatus.textContent = 'STANDBY';
    this.tickerMessage.textContent = 'Kernel idle. Ready to receive operator directives.';

    Object.values(this.steps).forEach(step => {
      step.el.className = 'pipeline-step';
      step.stateEl.textContent = 'Awaiting input';
      step.descEl.textContent = step.defaultDesc;
    });
  }

  updateStepUI(phase, status, message) {
    const step = this.steps[phase];
    if (!step) return;

    step.el.classList.remove('step-running', 'step-completed', 'step-warning', 'step-failed');

    if (status === 'IN_PROGRESS') {
      step.el.classList.add('step-running');
      step.stateEl.textContent = 'PROCESSING...';
      if (message) step.descEl.textContent = message;
    } else if (status === 'COMPLETED') {
      step.el.classList.add('step-completed');
      step.stateEl.textContent = 'VERIFIED';
      if (message) step.descEl.textContent = message;
    } else if (status === 'NEEDS_CONFIRMATION') {
      step.el.classList.add('step-warning');
      step.stateEl.textContent = 'REQUIRES CONFIRMATION';
      if (message) step.descEl.textContent = message;
    } else if (status === 'FAILED') {
      step.el.classList.add('step-failed');
      step.stateEl.textContent = 'EXCEPTION';
      if (message) step.descEl.textContent = message;
    }

    if (message) {
      this.tickerMessage.textContent = `[${phase}] ${message}`;
    }
  }

  async handleExecute() {
    const promptText = this.promptInput.value.trim();
    if (!promptText || this.isProcessing) return;

    this.isProcessing = true;
    this.setControlsDisabled(true);
    this.hideErrorBanner();
    this.resetPipelineUI();

    this.pipelineGlobalStatus.className = 'status-badge badge-running';
    this.pipelineGlobalStatus.textContent = 'EXECUTING';

    this.renderLoadingResult(promptText);

    try {
      const result = await this.engine.executePrompt(promptText, (progress) => {
        this.updateStepUI(progress.phase, progress.status, progress.message);
      });

      if (result.status === 'AWAITING_CONFIRMATION') {
        this.showConfirmationModal(result);
        return; // Execution paused waiting for operator
      }

      // Normal Completion
      this.handleExecutionSuccess(result);

    } catch (err) {
      this.handleExecutionError(err);
    } finally {
      if (!this.activeActionId) {
        this.isProcessing = false;
        this.setControlsDisabled(false);
      }
    }
  }

  isModalVisible() {
    return (
      !this.confirmOverlay.hidden ||
      this.confirmOverlay.classList.contains('active') ||
      this.confirmOverlay.style.display === 'flex' ||
      !this.confirmOverlay.hasAttribute('hidden')
    );
  }

  showConfirmationModal(req) {
    this.activeActionId = req.actionId;
    this.modalActionName.textContent = req.actionLabel || 'High-Risk Operation';
    this.modalTargetResource.textContent = req.targetResource || 'System Protected Resource';
    this.modalWarningText.textContent = req.warning;

    // Show modal overlay reliably
    this.confirmOverlay.removeAttribute('hidden');
    this.confirmOverlay.hidden = false;
    this.confirmOverlay.classList.add('active');
    this.confirmOverlay.style.display = 'flex';

    this.pipelineGlobalStatus.className = 'status-badge badge-warning';
    this.pipelineGlobalStatus.textContent = 'WAITING CONFIRMATION';
    this.modalConfirmBtn.focus();
  }

  closeConfirmationModal() {
    this.confirmOverlay.setAttribute('hidden', '');
    this.confirmOverlay.hidden = true;
    this.confirmOverlay.classList.remove('active');
    this.confirmOverlay.style.display = 'none';
  }

  async handleConfirmAction() {
    if (!this.activeActionId) return;
    const actionId = this.activeActionId;
    this.activeActionId = null;

    // Close modal immediately
    this.closeConfirmationModal();

    this.pipelineGlobalStatus.className = 'status-badge badge-running';
    this.pipelineGlobalStatus.textContent = 'RESUMING';

    try {
      const result = await this.engine.confirmAction(actionId, (progress) => {
        this.updateStepUI(progress.phase, progress.status, progress.message);
      });
      this.handleExecutionSuccess(result);
    } catch (err) {
      this.handleExecutionError(err);
    } finally {
      this.isProcessing = false;
      this.setControlsDisabled(false);
    }
  }

  handleCancelConfirmation() {
    const actionId = this.activeActionId;
    this.activeActionId = null;

    // 1. Close modal immediately
    this.closeConfirmationModal();

    // 2. Abort simulated action token in engine
    let cancelMessage = 'Action cancelled by user. Pending simulated execution aborted.';
    if (actionId) {
      const cancelRes = this.engine.cancelAction(actionId);
      if (cancelRes && cancelRes.message) {
        cancelMessage = cancelRes.message;
      }
    }

    // 3. Update status & pipeline indicators
    this.pipelineGlobalStatus.className = 'status-badge badge-warning';
    this.pipelineGlobalStatus.textContent = 'ACTION CANCELLED';
    this.tickerMessage.textContent = cancelMessage;

    // Mark permission step as cancelled
    const permStep = this.steps.PERMISSION_CHECK;
    permStep.el.className = 'pipeline-step step-warning';
    permStep.stateEl.textContent = 'USER ABORTED';
    permStep.descEl.textContent = 'Action cancelled by user. No system commands or modifications were made.';

    // Reset subsequent pipeline steps to standby
    const execStep = this.steps.AGENT_EXECUTION;
    execStep.el.className = 'pipeline-step';
    execStep.stateEl.textContent = 'STANDBY';
    execStep.descEl.textContent = execStep.defaultDesc;

    const resStep = this.steps.RESULT_SYNTHESIS;
    resStep.el.className = 'pipeline-step';
    resStep.stateEl.textContent = 'STANDBY';
    resStep.descEl.textContent = resStep.defaultDesc;

    // 4. Render clear "Action cancelled by user" card in result panel
    this.renderCancelledResult();

    // 5. Re-enable prompt controls and return focus to prompt
    this.isProcessing = false;
    this.setControlsDisabled(false);
    this.promptInput.focus();
  }

  handleExecutionSuccess(result) {
    this.pipelineGlobalStatus.className = 'status-badge badge-success';
    this.pipelineGlobalStatus.textContent = 'COMPLETED';

    this.metaLatency.textContent = `LATENCY: ${result.metrics?.latencyMs || 850}ms`;
    this.metaRisk.textContent = result.isDestructiveSimulated ? 'RISK: HIGH (CONFIRMED)' : `RISK: ${result.riskLevel || 'SAFE'}`;

    this.renderResult(result);
  }

  handleExecutionError(err) {
    this.pipelineGlobalStatus.className = 'status-badge badge-error';
    this.pipelineGlobalStatus.textContent = 'FAULT';

    // Show simulated error panel
    this.errorCode.textContent = `ERROR_CODE: ${err.code || 'SIM_ERR_EXEC_FAILURE'}`;
    this.errorMessage.textContent = err.message || 'An unexpected fault occurred during simulated processing.';
    
    if (err.details) {
      this.errSubsystem.textContent = err.details.subsystem || 'Core';
      this.errVector.textContent = err.details.vector || 'Runtime Fault';
      this.errRecovery.textContent = err.details.recovery || 'Re-try with a standard query';
    } else {
      this.errSubsystem.textContent = 'Kernel Dispatcher';
      this.errVector.textContent = 'Execution Failure';
      this.errRecovery.textContent = 'Verify request syntax and re-submit';
    }

    this.errorBanner.hidden = false;

    // Render error in result panel
    this.resultDisplay.innerHTML = `
      <div class="result-card-inner">
        <div class="result-text-box" style="border-color: rgba(239, 68, 68, 0.4);">
          <h3 style="color: #ef4444;">Simulation Error Encountered</h3>
          <p>${this.escapeHtml(err.message)}</p>
          <blockquote>The AgenticOS execution kernel safely trapped this simulated exception. You can dismiss the error or test another prompt.</blockquote>
        </div>
      </div>
    `;

    this.metaLatency.textContent = 'LATENCY: FAILED';
    this.metaRisk.textContent = 'RISK: FAULT TRIGGERED';
  }

  hideErrorBanner() {
    this.errorBanner.hidden = true;
  }

  setControlsDisabled(disabled) {
    this.executeBtn.disabled = disabled;
    this.clearBtn.disabled = disabled;
    this.promptInput.disabled = disabled;
    this.presetChips.forEach(chip => chip.disabled = disabled);
    this.executeBtn.querySelector('.btn-text').textContent = disabled ? 'Processing...' : 'Execute';
  }

  renderLoadingResult(prompt) {
    this.resultDisplay.innerHTML = `
      <div class="empty-state">
        <div class="step-spinner" style="display: block; position: static; width: 32px; height: 32px; border-width: 3px; margin-bottom: 1rem;"></div>
        <p class="empty-text">Processing Directive</p>
        <span class="empty-sub">"${this.escapeHtml(prompt)}"</span>
      </div>
    `;
  }

  renderCancelledResult() {
    this.metaLatency.textContent = 'LATENCY: ABORTED';
    this.metaRisk.textContent = 'STATUS: CANCELLED BY USER';

    this.resultDisplay.innerHTML = `
      <div class="result-card-inner">
        <div class="result-text-box" style="border-color: rgba(245, 158, 11, 0.4); background: rgba(245, 158, 11, 0.04);">
          <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.6rem;">
            <span style="font-size: 1.25rem;">⚠️</span>
            <h3 style="color: var(--accent-amber); margin: 0;">Action Cancelled by User</h3>
          </div>
          <p style="color: var(--text-main); margin-bottom: 0.75rem;">
            The requested sensitive action was aborted by the operator. The pending simulated operation was cancelled and was not executed.
          </p>
          <blockquote style="border-left-color: var(--accent-amber); color: #fde68a;">
            <strong>AgenticOS Security Guarantee:</strong> Zero commands were dispatched. No filesystem, partition, or process state was altered.
          </blockquote>
        </div>

        <div class="audit-terminal">
          <div class="audit-terminal-header">
            <span>AGENTICOS_AUDIT_LOG_STREAM</span>
            <span style="color: var(--accent-amber);">STATUS: ACTION_CANCELLED</span>
          </div>
          <div class="audit-terminal-body">
            <div class="audit-line dim">❯ [AUDIT] High-risk intent intercepted by Policy Kernel</div>
            <div class="audit-line dim">❯ [AUDIT] Operator manual confirmation requested</div>
            <div class="audit-line" style="color: var(--accent-amber);">❯ [AUDIT] Action cancelled by user</div>
            <div class="audit-line" style="color: #6ee7b7;">❯ [AUDIT] Temporary execution token revoked and destroyed</div>
            <div class="audit-line dim">❯ [AUDIT] Returned to main prompt interface safely</div>
          </div>
        </div>
      </div>
    `;
  }

  renderResult(res) {
    const formattedHtml = this.formatMarkdownToHtml(res.responseText);
    const auditLinesHtml = (res.auditLog || [])
      .map(line => `<div class="audit-line ${line.startsWith('[AUDIT]') ? 'dim' : ''}">❯ ${this.escapeHtml(line)}</div>`)
      .join('');

    this.resultDisplay.innerHTML = `
      <div class="result-card-inner">
        <div class="result-text-box">
          ${formattedHtml}
        </div>

        <div class="audit-terminal">
          <div class="audit-terminal-header">
            <span>AGENTICOS_AUDIT_LOG_STREAM</span>
            <span>STATUS: NOMINAL</span>
          </div>
          <div class="audit-terminal-body">
            ${auditLinesHtml}
          </div>
        </div>
      </div>
    `;
  }

  formatMarkdownToHtml(markdown) {
    if (!markdown) return '';
    let html = markdown
      // Headers
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      // Bold
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      // Italic
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      // Blockquote
      .replace(/^> (.*$)/gim, '<blockquote>$1</blockquote>')
      // Unordered lists
      .replace(/^\* (.*$)/gim, '<li>$1</li>')
      // Line breaks
      .replace(/\n\n/g, '<br><br>');

    // Wrap list items in <ul>
    html = html.replace(/(<li>.*<\/li>)/gims, '<ul>$1</ul>');
    return html;
  }

  escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

// Bootstrap once DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.__agenticOS = new AgenticOSApp();
});
