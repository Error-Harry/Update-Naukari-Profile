import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, getToken, setToken, type Me } from "./api";

export function useAuthToken() {
  const [token, setTok] = useState<string | null>(getToken());

  useEffect(() => {
    const onChange = () => setTok(getToken());
    window.addEventListener("auth-changed", onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener("auth-changed", onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  return token;
}

export function useMe() {
  const token = useAuthToken();
  return useQuery({
    queryKey: ["me", token],
    queryFn: () => api<Me>("/api/me"),
    enabled: !!token,
    retry: false,
  });
}

export function logout() {
  setToken(null);
}

export { getToken, setToken };
