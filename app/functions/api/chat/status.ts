interface Env {
  LLM_BASE_URL?: string
  LLM_API_KEY?: string
  LLM_MODEL?: string
}

/** Report configuration without revealing the endpoint or credential. */
export const onRequestGet = ({ env }: { env: Env }) => {
  const configured = [env.LLM_BASE_URL, env.LLM_API_KEY, env.LLM_MODEL]
    .every((value) => Boolean(value?.trim()))
  return Response.json({ llm_configured: configured, model: configured ? env.LLM_MODEL : null }, {
    headers: { 'Cache-Control': 'no-store' },
  })
}
