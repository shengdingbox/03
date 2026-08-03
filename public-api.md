# 公开接口文档（无需鉴权）

> 所有接口均无需登录鉴权，可直接调用。  
> Base URL: `http://127.0.0.1:5000`（本地）或部署地址  
> 最后更新：2026-08-03

## 加密说明

部分接口需要**加密签名**，部分接口为**明文**调用。标注如下：

- **明文**：直接发送 JSON / Query 参数，返回明文 JSON
- **加密**：请求需携带 `X-Signature` 等签名头，Body 为加密密文，响应为加密密文
  - 签名算法：HMAC-SHA256
  - 加密算法：AES-GCM

---

## 1. 用户积分查询

| 属性 | 值 |
|------|------|
| 方法 | `GET` |
| 路径 | `/api/user/credits` |
| 加密 | **明文** |

**请求**

```
GET /api/user/credits?userKey={userKey}
```

| 参数 | 位置 | 必填 | 说明 |
|------|------|------|------|
| userKey | query | 是 | 用户 API Key（如 `sk-xxxx`） |

**响应**

```json
{
  "credits": 9950.0,
  "totalUsed": 50.0,
  "totalRecharged": 10000.0,
  "todayUsed": 30.0,
  "todayRank": 1,
  "userKey": "sk-xxxx"
}
```

---

## 2. 今日使用记录

| 属性 | 值 |
|------|------|
| 方法 | `GET` |
| 路径 | `/api/user/today-usage` |
| 加密 | **明文** |

**请求**

```
GET /api/user/today-usage?userKey={userKey}
```

| 参数 | 位置 | 必填 | 说明 |
|------|------|------|------|
| userKey | query | 是 | 用户 API Key |

**响应**

```json
{
  "records": [
    {
      "id": "...",
      "userKey": "sk-xxxx",
      "amount": 0.03,
      "balanceAfter": 9970.0,
      "model": "glm-5.2",
      "nodeId": "...",
      "tokens": 300,
      "createdAt": "2026-08-03 14:00:00"
    }
  ]
}
```

---

## 3. 卡密兑换

| 属性 | 值 |
|------|------|
| 方法 | `POST` |
| 路径 | `/api/redeem` |
| 加密 | **加密**（需签名头 + 加密 Body，返回加密 JSON） |

**请求**

```
POST /api/redeem
```

加密 Body 解密后：

```json
{
  "cardKey": "CARD-XXXX",
  "userKey": "sk-xxxx"
}
```

| 参数 | 位置 | 必填 | 说明 |
|------|------|------|------|
| cardKey | body | 是 | 卡密 |
| userKey | body | 是 | 用户 API Key |

**响应**（加密，解密后）

```json
{
  "success": true,
  "credits": 10000.0,
  "message": "兑换成功"
}
```

---

## 4. 激活卡密

| 属性 | 值 |
|------|------|
| 方法 | `POST` |
| 路径 | `/api/activate` |
| 加密 | **明文** |

**请求**

```
POST /api/activate
Content-Type: application/json
```

```json
{
  "cardKey": "CARD-XXXX"
}
```

| 参数 | 位置 | 必填 | 说明 |
|------|------|------|------|
| cardKey | body | 是 | 卡密 |

**响应**

```json
{
  "success": true,
  "apiKey": "sk-xxxx",
  "credits": 10000.0,
  "message": "激活成功"
}
```

---

## 5. 获取 Buddy Key

| 属性 | 值 |
|------|------|
| 方法 | `POST` |
| 路径 | `/api/buddykey/get` |
| 加密 | **加密**（需签名头 + 加密 Body，返回加密 JSON） |

**请求**

```
POST /api/buddykey/get
```

加密 Body 解密后：

```json
{
  "userKey": "sk-xxxx"
}
```

**响应**（加密，解密后）

```json
{
  "success": true,
  "buddyKey": "BC-xxxx"
}
```

---

## 6. 上报使用记录

| 属性 | 值 |
|------|------|
| 方法 | `POST` |
| 路径 | `/api/usage/report` |
| 加密 | **加密**（需签名头 + 加密 Body，返回加密 JSON） |

**请求**

加密 Body 解密后：

```json
{
  "device_fingerprint": "sk-xxxx",
  "credits_used": 0.03,
  "model": "glm-5.2",
  "prompt_tokens": 100,
  "completion_tokens": 200
}
```

**响应**（加密，解密后）

```json
{
  "success": true
}
```

---

## 7. 模型列表（明文，OpenAI 兼容）

| 属性 | 值 |
|------|------|
| 方法 | `GET` |
| 路径 | `/v1/models` 或 `/api/proxy/models` |
| 加密 | **明文** |

无参数。

**响应**

```json
{
  "object": "list",
  "data": [
    {
      "id": "glm-5.2",
      "object": "model",
      "created": 0,
      "vendor": "buddy",
      "name": "WB-GLM-5.2",
      "maxInputTokens": 1000000,
      "maxOutputTokens": 8192,
      "supportsToolCall": true,
      "supportsImages": true,
      "supportsReasoning": true
    }
  ]
}
```

---

## 8. 模型列表（加密）

| 属性 | 值 |
|------|------|
| 方法 | `POST` |
| 路径 | `/api/models/list` |
| 加密 | **加密**（需签名头，返回加密 JSON） |

**请求**

```
POST /api/models/list
```

需加密签名（`X-Signature` 等请求头）。

**响应**（加密，解密后）

同接口 7 的 data 字段。

---

## 9. 服务端点列表

| 属性 | 值 |
|------|------|
| 方法 | `GET` |
| 路径 | `/api/server_endpoints` 或 `/v1/server_endpoints` |
| 加密 | **明文** |

无参数。返回所有启用的服务端点。

**响应**

```json
{
  "success": true,
  "data": [
    {
      "id": "abc12345",
      "name": "华东节点1",
      "url": "https://47.108.236.176",
      "region": "华东",
      "sortOrder": 0
    }
  ]
}
```

---

## 10. 版本检测（明文 GET）

| 属性 | 值 |
|------|------|
| 方法 | `GET` |
| 路径 | `/api/version/check` 或 `/v1/version/check` |
| 加密 | **明文** |

**请求**

```
GET /api/version/check?platform={platform}&version={version}
```

| 参数 | 位置 | 必填 | 说明 |
|------|------|------|------|
| platform | query | 否 | 平台（win/mac，默认 win） |
| version | query | 否 | 当前版本号（如 `1.0.0`） |

**响应**

```json
{
  "success": true,
  "hasUpdate": true,
  "version": "1.2.0",
  "latestVersion": "1.2.0",
  "platform": "win",
  "downloadUrl": "https://...",
  "changelog": "修复若干问题",
  "minVersion": "1.0.0",
  "isForceUpdate": false,
  "createdAt": "2026-08-03 10:00:00"
}
```

---

## 11. 版本检测（加密 POST）

| 属性 | 值 |
|------|------|
| 方法 | `POST` |
| 路径 | `/api/version/check` |
| 加密 | **加密**（需签名头 + 加密 Body，返回加密 JSON） |

需加密签名（`X-Signature` 等请求头）。返回加密 JSON。

---

## 接口汇总表

| # | 方法 | 路径 | 加密 | 说明 |
|---|------|------|------|------|
| 1 | GET | `/api/user/credits` | 明文 | 查询积分 |
| 2 | GET | `/api/user/today-usage` | 明文 | 今日使用记录 |
| 3 | POST | `/api/redeem` | **加密** | 卡密兑换 |
| 4 | POST | `/api/activate` | 明文 | 激活卡密 |
| 5 | POST | `/api/buddykey/get` | **加密** | 获取 Buddy Key |
| 6 | POST | `/api/usage/report` | **加密** | 上报使用记录 |
| 7 | GET | `/v1/models`、`/api/proxy/models` | 明文 | 模型列表（OpenAI 兼容） |
| 8 | POST | `/api/models/list` | **加密** | 模型列表 |
| 9 | GET | `/api/server_endpoints`、`/v1/server_endpoints` | 明文 | 服务端点列表 |
| 10 | GET | `/api/version/check`、`/v1/version/check` | 明文 | 版本检测 |
| 11 | POST | `/api/version/check` | **加密** | 版本检测 |

### 加密接口一览（共 5 个）

| # | 接口 | 说明 |
|---|------|------|
| 3 | `POST /api/redeem` | 卡密兑换 |
| 5 | `POST /api/buddykey/get` | 获取 Buddy Key |
| 6 | `POST /api/usage/report` | 上报使用记录 |
| 8 | `POST /api/models/list` | 模型列表 |
| 11 | `POST /api/version/check` | 版本检测 |

### 明文接口一览（共 6 个）

| # | 接口 | 说明 |
|---|------|------|
| 1 | `GET /api/user/credits` | 查询积分 |
| 2 | `GET /api/user/today-usage` | 今日使用记录 |
| 4 | `POST /api/activate` | 激活卡密 |
| 7 | `GET /v1/models`、`/api/proxy/models` | 模型列表 |
| 9 | `GET /api/server_endpoints`、`/v1/server_endpoints` | 服务端点列表 |
| 10 | `GET /api/version/check`、`/v1/version/check` | 版本检测 |
