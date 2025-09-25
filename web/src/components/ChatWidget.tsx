import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent
} from 'react';
import { API_ENDPOINTS, DEFAULT_HEADERS } from '../config/api.ts';
import type {
  ChatMessage,
  ReservationDecisionAction,
  ReservationProposal,
  StreamEvent,
  ToolEventPayload
} from '../types/chat.ts';
import '../styles/chat-widget.css';

const AVATARS: Record<ChatMessage['role'], string> = {
  assistant: '🤖',
  user: '🙂',
  system: 'ℹ️'
};

const formatDateTime = (value?: string) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
};

const createSessionId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
};

const INITIAL_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content: '您好，我是预约助手，很高兴为您服务。告诉我您想预约的设备与时间即可开始。',
  createdAt: Date.now(),
  type: 'text'
};

const ChatWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [hasUnread, setHasUnread] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeAssistantMessageId, setActiveAssistantMessageId] = useState<string | null>(null);
  const [sessionId] = useState(createSessionId);
  const [pendingProposal, setPendingProposal] = useState<ReservationProposal | null>(null);
  const [decisionLoading, setDecisionLoading] = useState<ReservationDecisionAction | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const queuedProposalRef = useRef<ReservationProposal | null>(null);

  const assistantName = useMemo(() => '预约智能体', []);

  const appendMessage = useCallback(
    (message: ChatMessage) => {
      setMessages((prev) => [...prev, message]);
      if (message.role === 'assistant' && !isOpen) {
        setHasUnread(true);
      }
    },
    [isOpen]
  );

  useEffect(() => {
    if (isOpen) {
      setHasUnread(false);
      // Delay ensures DOM updated before scroll
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      });
    }
  }, [isOpen, messages.length]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => () => abortControllerRef.current?.abort(), []);

  const updateMessageContent = useCallback((id: string, content: string) => {
    setMessages((prev) => prev.map((msg) => (msg.id === id ? { ...msg, content } : msg)));
  }, []);

  const handleToolEvent = useCallback(
    (event: ToolEventPayload) => {
      if (event.tool_name === 'check_device_availability') {
        const output = event.output ?? {};
        const isAvailable = typeof output === 'object' && output !== null && 'available' in output ? Boolean((output as any).available) : false;

        if (isAvailable) {
          const proposalRaw = (output as any).proposal ?? output;
          const proposal: ReservationProposal | null =
            proposalRaw && typeof proposalRaw === 'object'
              ? {
                  resource_id: String((proposalRaw as any).resource_id ?? ''),
                  start_time: String((proposalRaw as any).start_time ?? ''),
                  end_time: (proposalRaw as any).end_time ? String((proposalRaw as any).end_time) : undefined,
                  reservation_id: (proposalRaw as any).reservation_id
                    ? String((proposalRaw as any).reservation_id)
                    : undefined,
                  note: (proposalRaw as any).note ? String((proposalRaw as any).note) : undefined
                }
              : null;

          if (proposal && proposal.resource_id && proposal.start_time) {
            queuedProposalRef.current = proposal;
            setPendingProposal(null);
          } else {
            queuedProposalRef.current = null;
            setPendingProposal(null);
            appendMessage({
              id: crypto.randomUUID(),
              role: 'system',
              content: '查询结果格式异常，暂无法展示预约选项。',
              createdAt: Date.now(),
              type: 'status'
            });
          }
        } else {
          queuedProposalRef.current = null;
          setPendingProposal(null);
          const reason = typeof (output as any).reason === 'string' ? (output as any).reason : null;
          appendMessage({
            id: crypto.randomUUID(),
            role: 'system',
            content: reason ?? '当前暂无符合条件的空闲资源，请尝试调整需求。',
            createdAt: Date.now(),
            type: 'status'
          });
        }
      }

      if (event.tool_name === 'update_reservation_status') {
        const output = event.output ?? {};
        const success = typeof output === 'object' && output !== null && 'success' in output ? Boolean((output as any).success) : false;
        const reason = typeof (output as any).reason === 'string' ? (output as any).reason : null;
        if (success) {
          queuedProposalRef.current = null;
          setPendingProposal(null);
          appendMessage({
            id: crypto.randomUUID(),
            role: 'system',
            content: '预约已更新完成。',
            createdAt: Date.now(),
            type: 'status'
          });
        } else {
          queuedProposalRef.current = null;
          appendMessage({
            id: crypto.randomUUID(),
            role: 'system',
            content: reason ?? '预约更新失败，请稍后重试或重新发起请求。',
            createdAt: Date.now(),
            type: 'status'
          });
        }
      }
    },
    [appendMessage]
  );

  const streamAssistantResponse = useCallback(
    async (userMessage: string) => {
      setIsStreaming(true);
      setActiveAssistantMessageId(null);
      const controller = new AbortController();
      abortControllerRef.current = controller;

      let assistantMessageId: string | null = null;
      let assembledContent = '';

      const ensureAssistantMessage = (content: string) => {
        if (!assistantMessageId) {
          assistantMessageId = crypto.randomUUID();
          setActiveAssistantMessageId(assistantMessageId);
          appendMessage({
            id: assistantMessageId,
            role: 'assistant',
            content,
            createdAt: Date.now(),
            type: 'text'
          });
        } else {
          updateMessageContent(assistantMessageId, content);
        }
      };

      const flushQueuedProposal = () => {
        if (queuedProposalRef.current) {
          setPendingProposal(queuedProposalRef.current);
          queuedProposalRef.current = null;
        }
      };

      try {
        const response = await fetch(API_ENDPOINTS.chatStream, {
          method: 'POST',
          headers: {
            ...DEFAULT_HEADERS,
            Accept: 'application/x-ndjson'
          },
          body: JSON.stringify({
            session_id: sessionId,
            message: userMessage
          }),
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`请求失败 (${response.status})`);
        }

        if (!response.body) {
          throw new Error('服务器未返回内容');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        const processLine = (line: string) => {
          if (!line) return;
          try {
            const event = JSON.parse(line) as StreamEvent;
            if (event.type === 'token') {
              assembledContent += event.content;
              if (assembledContent) {
                ensureAssistantMessage(assembledContent);
              }
            } else if (event.type === 'message') {
              assembledContent = event.content;
              ensureAssistantMessage(assembledContent);
              flushQueuedProposal();
            } else if (event.type === 'tool') {
              handleToolEvent(event);
            } else if (event.type === 'done') {
              flushQueuedProposal();
            }
          } catch (error) {
            console.error('无法解析流数据:', error);
          }
        };

        while (true) {
          const { value, done } = await reader.read();
          if (value) {
            buffer += decoder.decode(value, { stream: !done });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';
            for (const rawLine of lines) {
              const line = rawLine.trim();
              if (line) {
                processLine(line);
              }
            }
          }

          if (done) {
            break;
          }
        }

        buffer += decoder.decode();
        const remaining = buffer.trim();
        if (remaining) {
          processLine(remaining);
        }
        flushQueuedProposal();
      } catch (error) {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          const fallback = '抱歉，处理请求时出现问题，请稍后再试。';
          if (assistantMessageId) {
            updateMessageContent(assistantMessageId, fallback);
          } else {
            ensureAssistantMessage(fallback);
          }
          appendMessage({
            id: crypto.randomUUID(),
            role: 'system',
            content: error instanceof Error ? `错误信息: ${error.message}` : '未知错误',
            createdAt: Date.now(),
            type: 'status'
          });
        }
      } finally {
        setIsStreaming(false);
        setActiveAssistantMessageId(null);
        abortControllerRef.current = null;
      }
    },
    [appendMessage, handleToolEvent, sessionId, updateMessageContent]
  );

  const processUserMessage = useCallback(
    async (message: string) => {
      appendMessage({
        id: crypto.randomUUID(),
        role: 'user',
        content: message,
        createdAt: Date.now(),
        type: 'text'
      });
      await streamAssistantResponse(message);
    },
    [appendMessage, streamAssistantResponse]
  );

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const trimmed = inputValue.trim();
      if (!trimmed || isStreaming) {
        return;
      }
      setInputValue('');
      await processUserMessage(trimmed);
    },
    [inputValue, isStreaming, processUserMessage]
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        const trimmed = inputValue.trim();
        if (!trimmed || isStreaming) {
          return;
        }
        setInputValue('');
        processUserMessage(trimmed);
      }
    },
    [inputValue, isStreaming, processUserMessage]
  );

  const handleReservationDecision = useCallback(
    async (action: ReservationDecisionAction) => {
      if (!pendingProposal) {
        return;
      }

      if (action === 'cancel' && !pendingProposal.reservation_id) {
        queuedProposalRef.current = null;
        setPendingProposal(null);
        appendMessage({
          id: crypto.randomUUID(),
          role: 'system',
          content: '已取消本次预约建议，若需要可重新询问。',
          createdAt: Date.now(),
          type: 'status'
        });
        return;
      }

      if (action === 'confirm' && !pendingProposal.start_time) {
        queuedProposalRef.current = null;
        appendMessage({
          id: crypto.randomUUID(),
          role: 'system',
          content: '缺少预约时间，暂无法提交预约。',
          createdAt: Date.now(),
          type: 'status'
        });
        return;
      }

      setDecisionLoading(action);

      const payload: Record<string, unknown> = {
        session_id: sessionId,
        action
      };

      if (action === 'confirm') {
        payload.start_time = pendingProposal.start_time;
      } else if (action === 'cancel' && pendingProposal.reservation_id) {
        payload.reservation_id = pendingProposal.reservation_id;
      }

      try {
        const response = await fetch(API_ENDPOINTS.reservationDecision, {
          method: 'POST',
          headers: DEFAULT_HEADERS,
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          throw new Error(`操作失败 (${response.status})`);
        }

        const payloadJson = await response.json();
        const assistantMessage =
          typeof payloadJson?.assistant_message === 'string' ? payloadJson.assistant_message : '';
        const schedulerSuccess = Boolean(payloadJson?.scheduler?.success);
        const schedulerReason =
          typeof payloadJson?.scheduler?.reason === 'string' ? payloadJson.scheduler.reason : null;

        if (assistantMessage) {
          appendMessage({
            id: crypto.randomUUID(),
            role: 'assistant',
            content: assistantMessage,
            createdAt: Date.now(),
            type: 'text'
          });
        }

        if (schedulerSuccess) {
          queuedProposalRef.current = null;
          setPendingProposal(null);
        } else if (schedulerReason) {
          appendMessage({
            id: crypto.randomUUID(),
            role: 'system',
            content: schedulerReason,
            createdAt: Date.now(),
            type: 'status'
          });
        }
      } catch (error) {
        appendMessage({
          id: crypto.randomUUID(),
          role: 'system',
          content: error instanceof Error ? `操作未完成：${error.message}` : '操作未完成，发生未知错误。',
          createdAt: Date.now(),
          type: 'status'
        });
      } finally {
        setDecisionLoading(null);
        if (action === 'cancel') {
          setPendingProposal(null);
          queuedProposalRef.current = null;
        }
      }
    },
    [appendMessage, pendingProposal, sessionId]
  );

  const hasPendingAction = Boolean(pendingProposal);

  return (
    <>
      <button
        className="chat-floating-button"
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label="打开预约聊天"
      >
        {hasUnread ? '💬' : '🔆'}
      </button>

      {isOpen && (
        <section className="chat-panel" role="dialog" aria-modal="true" aria-label="预约智能体对话">
          <div className="chat-panel__header">
            <h2>{assistantName}</h2>
            <p className="chat-panel__header-controls">随时与我沟通，快速完成设备预约。</p>
            <button
              className="chat-panel__close"
              type="button"
              onClick={() => setIsOpen(false)}
              aria-label="关闭对话"
            >
              ×
            </button>
          </div>

          <div className="chat-panel__messages">
            {messages.map((message) => (
              <div key={message.id} className={`chat-message ${message.role}`}>
                <div className="chat-message__avatar">{AVATARS[message.role]}</div>
                <div className="chat-message__bubble">{message.content}</div>
              </div>
            ))}

            {hasPendingAction && pendingProposal && (
              <div className="chat-message assistant">
                <div className="chat-message__avatar">{AVATARS.assistant}</div>
                <div className="chat-message__bubble">
                  <div className="reservation-card">
                    <div className="reservation-card__header">预约详情确认</div>
                    <div className="reservation-card__meta">
                      <span>资源：{pendingProposal.resource_id}</span>
                      <span>开始：{formatDateTime(pendingProposal.start_time)}</span>
                      {pendingProposal.end_time && (
                        <span>结束：{formatDateTime(pendingProposal.end_time)}</span>
                      )}
                    </div>
                    {pendingProposal.note && (
                      <p className="reservation-card__note">{pendingProposal.note}</p>
                    )}
                    <div className="reservation-card__actions">
                      <button
                        className="confirm"
                        type="button"
                        onClick={() => handleReservationDecision('confirm')}
                        disabled={decisionLoading === 'confirm'}
                      >
                        {decisionLoading === 'confirm' ? '提交中...' : '提交预约'}
                      </button>
                      <button
                        className="cancel"
                        type="button"
                        onClick={() => handleReservationDecision('cancel')}
                        disabled={decisionLoading === 'cancel'}
                      >
                        {decisionLoading === 'cancel' ? '取消中...' : '暂不预约'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {isStreaming && !activeAssistantMessageId && (
              <div className="chat-message assistant">
                <div className="chat-message__avatar">{AVATARS.assistant}</div>
                <div className="chat-message__bubble">
                  <span className="chat-typing-indicator">正在输入...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-panel__input">
            <form className="chat-input-form" onSubmit={handleSubmit}>
              <textarea
                placeholder="例如：帮我预约明天早上8点的设备"
                value={inputValue}
                onChange={(event) => setInputValue(event.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isStreaming}
              />
              <button type="submit" disabled={isStreaming || !inputValue.trim()}>
                发送
              </button>
            </form>
          </div>
        </section>
      )}
    </>
  );
};

export default ChatWidget;
