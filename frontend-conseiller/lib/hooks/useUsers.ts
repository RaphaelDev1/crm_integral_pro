"use client";

import { createResourceHooks } from "@/lib/hooks/useResource";
import type { UserCreateInput, UserUpdateInput } from "@/lib/schemas/user";
import type { User } from "@/lib/types";

export const usersResource = createResourceHooks<User, UserCreateInput, UserUpdateInput>("users", "/users");
