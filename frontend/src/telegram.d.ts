export {};

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        platform?: string;
        version?: string;
        colorScheme?: "light" | "dark";
        viewportHeight?: number;
        viewportStableHeight?: number;
        isExpanded?: boolean;
        ready(): void;
        expand(): void;
      };
    };
  }
}
