import { AnimatePresence, cubicBezier, motion } from 'framer-motion';

interface SendButtonProps {
  label?: string;
  show: boolean;
  isStreaming?: boolean;
  disabled?: boolean;
  onClick?: (event: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void;
  onImagesSelected?: (images: File[]) => void;
}

const customEasingFn = cubicBezier(0.4, 0, 0.2, 1);

export const SendButton = ({ show, label = 'Send →', isStreaming, disabled, onClick }: SendButtonProps) => {
  return (
    <AnimatePresence>
      {show ? (
        <motion.button
          className="absolute flex justify-center items-center bottom-[14px] right-[14px] gap-2 px-4 h-[38px] bg-[#4d8fe0] hover:brightness-110 text-white text-sm font-semibold rounded-lg shadow-md transition-theme disabled:opacity-50 disabled:cursor-not-allowed"
          transition={{ ease: customEasingFn, duration: 0.17 }}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          disabled={disabled}
          onClick={(event) => {
            event.preventDefault();

            if (!disabled) {
              onClick?.(event);
            }
          }}
        >
          {isStreaming ? <div className="i-ph:stop-circle-bold text-lg"></div> : <span>{label}</span>}
        </motion.button>
      ) : null}
    </AnimatePresence>
  );
};
