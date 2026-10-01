import type { APIRoute } from "astro";
import { proxyUpdate } from "../../../../../lib/update-proxy.ts";

export const GET: APIRoute = ({ params, request }) => proxyUpdate(params, request);
