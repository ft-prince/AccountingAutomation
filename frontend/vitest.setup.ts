import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// RTL only auto-cleans when the runner exposes globals; vitest here does not.
afterEach(cleanup);
