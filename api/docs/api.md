# API Documentation

Base URL: `/api`

## System

### GET `/api/health`
- **Description:** Basic health probe for uptime checks.
- **Response:**
  ```json
  {
    "status": "ok",
    "service": "Agent Demo API"
  }
  ```
- **Notes:** Returns the configured application name so the caller can confirm the deployed service.

## Agent

### POST `/api/agent/chat/stream`
- **Description:** Stream the conversation with the scheduling agent. Each request represents a single user turn and must include a stable `session_id` so the agent can load prior context.
- **Request body:**
  ```json
  {
    "session_id": "uuid-or-user-id",
    "message": "帮我预约明天早上8点的设备"
  }
  ```
- **Response:** NDJSON (`application/x-ndjson`) stream. Each line is a JSON object with a `type` field.
  - `token` – incremental assistant text tokens. `{ "type": "token", "content": "..." }`
  - `message` – full assistant message once the turn completes. `{ "type": "message", "content": "..." }`
  - `tool` – structured payloads emitted by LangGraph tools. Two tool names are currently used:
    - `check_device_availability` – responds with the availability result. Payload shape:
      ```json
      {
        "intent": "availability",
        "action_required": false,
        "available": true,
        "proposal": {
          "resource_id": "device-001",
          "start_time": "2025-09-25T02:00:00+00:00",
          "end_time": "2025-09-25T03:00:00+00:00"
        }
      }
      ```
      Use this to刷新对话内容和渲染“立即预约”按钮（若用户点了按钮，再调用确认接口）。
    - `update_reservation_status` – booking或取消的结果。Payload 例子：
      ```json
      {
        "intent": "booking_result",
        "action": "confirm",
        "action_required": false,
        "success": true,
        "reservation": {
          "reservation_id": "abc123",
          "resource_id": "device-001",
          "start_time": "2025-09-25T02:00:00+00:00",
          "end_time": "2025-09-25T03:00:00+00:00",
          "status": "confirmed"
        }
      }
      ```
  - `done` – signals the end of the stream for this turn.
- **Front-end guidance:**
  - Show the assistant's typing indicator while consuming `token` events.
  - 仅当 `intent == "availability"` 且 `available == true` 时显示预约按钮或交互提示；状态依旧是“未预约”，需要用户再操作。
  - 当 `intent == "booking_result"` 时，根据 `success` 更新 UI，并展示同轮对话中返回的 `assistant_message`。

### POST `/api/agent/reservations/decision`
- **Description:** Confirm or cancel a reservation based on the user's explicit action in the UI.
- **Request body:**
  ```json
  {
    "session_id": "uuid-or-user-id",
    "action": "confirm",            // or "cancel"
    "start_time": "2025-09-25T09:00:00+08:00", // required when action == "confirm"
    "reservation_id": "abc123"      // required when action == "cancel"
  }
  ```
- **Response:**
  ```json
  {
    "scheduler": {
      "intent": "booking_result",
      "action": "confirm",
      "action_required": false,
      "success": true,
      "reservation": {
        "reservation_id": "...",
        "resource_id": "device-001",
        "start_time": "2025-09-25T01:00:00+00:00",
        "end_time": "2025-09-25T02:00:00+00:00",
        "status": "confirmed"
      }
    },
    "assistant_message": "预约已确认，祝您使用顺利！"
  }
  ```
- **Notes:**
  - The endpoint immediately triggers the scheduler (mock) and feeds the outcome back into the agent so a follow-up assistant message is returned for display.
  - For `confirm`, supply the exact ISO 8601 `start_time` the user选定的时间段；`reservation_id` 对取消操作必填。

## Pending endpoints

Add new endpoints in this document as they are implemented so the front-end team can track request/response contracts.
