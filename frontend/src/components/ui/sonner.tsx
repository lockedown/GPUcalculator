"use client";

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast: "border border-gray-200 bg-white shadow-lg rounded-lg text-sm",
          title: "font-semibold text-gray-900",
          description: "text-gray-500 text-xs",
          actionButton: "bg-blue-600 text-white text-xs font-medium",
          cancelButton: "bg-gray-100 text-gray-600 text-xs font-medium",
          error: "border-red-200 bg-red-50",
          success: "border-green-200 bg-green-50",
        },
      }}
      richColors
      closeButton
    />
  );
}
