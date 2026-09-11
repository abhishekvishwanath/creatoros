import { ButtonHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";
import { motion } from "framer-motion";

type Variant = "primary" | "secondary" | "ghost";

const variantClasses: Record<Variant, string> = {
  primary: "bg-ink text-canvas hover:bg-ink/90",
  secondary: "bg-canvas-raised text-ink border border-border hover:bg-ink/5",
  ghost: "text-subtle hover:text-ink hover:bg-ink/5",
};

// framer-motion's motion.button redefines a few event handlers
// (onAnimationStart/End, onDrag*) with its own signatures that conflict
// with the native HTML ones — omit them since this component doesn't use
// any of them itself.
type NativeButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "onAnimationStart" | "onAnimationEnd" | "onDrag" | "onDragStart" | "onDragEnd"
>;

export const Button = forwardRef<HTMLButtonElement, NativeButtonProps & { variant?: Variant }>(
  ({ className, variant = "primary", ...props }, ref) => {
    return (
      <motion.button
        ref={ref}
        whileTap={{ scale: 0.97 }}
        transition={{ duration: 0.1 }}
        className={clsx(
          "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
          variantClasses[variant],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
