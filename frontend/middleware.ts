import { NextResponse, type NextRequest } from "next/server";
import { ROUTES } from "@/lib/routes";

// Django session cookie, proxied onto this origin by next.config.ts rewrites.
// Presence is a routing hint only; the API is the authority on validity.
const SESSION_COOKIE = "sessionid";
// /dev/* (token sheet, primitive gallery) is public for visual verification.
const PUBLIC_PREFIXES = ["/dev"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);
  const isLogin = pathname === ROUTES.login;
  const isPublic = PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));

  if (pathname === "/") {
    return NextResponse.redirect(new URL(hasSession ? ROUTES.dashboard : ROUTES.login, request.url));
  }
  if (isLogin && hasSession) {
    return NextResponse.redirect(new URL(ROUTES.dashboard, request.url));
  }
  if (!isLogin && !isPublic && !hasSession) {
    const login = new URL(ROUTES.login, request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  // Everything except Next internals, the API proxy, and static files.
  matcher: ["/((?!_next|api|favicon.ico|.*\\..*).*)"],
};
