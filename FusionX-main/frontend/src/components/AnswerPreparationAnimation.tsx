import { motion, AnimatePresence } from "motion/react";
import { MessageSquare, Sparkles, Lightbulb, Send, Bot } from "lucide-react";

interface AnswerPreparationAnimationProps {
  isActive: boolean;
  stage: "thinking" | "generating" | "validating" | "ready";
  progress?: number;
  message?: string;
}

export default function AnswerPreparationAnimation({ 
  isActive, 
  stage, 
  progress = 0, 
  message 
}: AnswerPreparationAnimationProps) {
  return (
    <AnimatePresence>
      {isActive && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/70 backdrop-blur-lg flex items-center justify-center z-50"
        >
          <motion.div
            initial={{ scale: 0.8, rotateX: -10 }}
            animate={{ scale: 1, rotateX: 0 }}
            exit={{ scale: 0.8, rotateX: -10 }}
            className="bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-900 border border-cyan-400/40 rounded-3xl p-8 max-w-md w-full mx-4 shadow-2xl"
            style={{ perspective: "1000px" }}
          >
            <div className="flex flex-col items-center space-y-6">
              {/* Animated Message/Bot Visualization */}
              <div className="relative w-28 h-28">
                {/* Central Message Bubble */}
                <motion.div
                  className="absolute inset-0 flex items-center justify-center"
                  animate={{
                    scale: [1, 1.05, 1],
                  }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <MessageSquare className="w-16 h-16 text-cyan-300" />
                </motion.div>

                {/* Orbiting Icons */}
                <motion.div
                  className="absolute w-8 h-8 bg-yellow-400 rounded-full flex items-center justify-center"
                  style={{ top: "0", left: "50%", transform: "translateX(-50%)" }}
                  animate={{
                    rotate: [0, 360],
                  }}
                  transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                >
                  <Lightbulb className="w-4 h-4 text-yellow-900" />
                </motion.div>

                <motion.div
                  className="absolute w-6 h-6 bg-purple-400 rounded-full flex items-center justify-center"
                  style={{ bottom: "10%", right: "10%" }}
                  animate={{
                    rotate: [0, -360],
                  }}
                  transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                >
                  <Sparkles className="w-3 h-3 text-purple-900" />
                </motion.div>

                <motion.div
                  className="absolute w-7 h-7 bg-green-400 rounded-full flex items-center justify-center"
                  style={{ top: "20%", right: "15%" }}
                  animate={{
                    rotate: [0, 360],
                  }}
                  transition={{ duration: 3.5, repeat: Infinity, ease: "linear", delay: 0.5 }}
                >
                  <Bot className="w-3 h-3 text-green-900" />
                </motion.div>

                {/* Sparkle Effects */}
                {stage === "generating" && [...Array(6)].map((_, i) => (
                  <motion.div
                    key={i}
                    className="absolute w-2 h-2 bg-cyan-400 rounded-full"
                    style={{
                      top: `${50 + Math.sin(i * 60 * Math.PI / 180) * 40}%`,
                      left: `${50 + Math.cos(i * 60 * Math.PI / 180) * 40}%`,
                    }}
                    animate={{
                      scale: [0, 1, 0],
                      opacity: [0, 1, 0]
                    }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      delay: i * 0.3
                    }}
                  />
                ))}
              </div>

              {/* Stage Indicator */}
              <div className="flex items-center space-x-3">
                {stage === "thinking" && (
                  <motion.div
                    animate={{ 
                      y: [0, -8, 0],
                      rotate: [0, 5, -5, 0]
                    }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <Lightbulb className="w-7 h-7 text-yellow-400" />
                  </motion.div>
                )}
                {stage === "generating" && (
                  <motion.div
                    animate={{ 
                      scale: [1, 1.3, 1],
                      rotate: [0, 180, 360]
                    }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  >
                    <Sparkles className="w-7 h-7 text-purple-400" />
                  </motion.div>
                )}
                {stage === "validating" && (
                  <motion.div
                    animate={{ 
                      x: [-5, 5, -5],
                      opacity: [0.7, 1, 0.7]
                    }}
                    transition={{ duration: 0.8, repeat: 3 }}
                  >
                    <Bot className="w-7 h-7 text-green-400" />
                  </motion.div>
                )}
                {stage === "ready" && (
                  <motion.div
                    initial={{ scale: 0, rotate: -180 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{ duration: 0.5, type: "spring" }}
                  >
                    <Send className="w-7 h-7 text-cyan-400" />
                  </motion.div>
                )}
              </div>

              {/* Progress Ring */}
              <div className="relative w-32 h-32">
                <svg className="absolute inset-0 w-full h-full transform -rotate-90">
                  <circle
                    cx="64"
                    cy="64"
                    r="56"
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth="8"
                    fill="none"
                  />
                  <motion.circle
                    cx="64"
                    cy="64"
                    r="56"
                    stroke="url(#gradient)"
                    strokeWidth="8"
                    fill="none"
                    strokeDasharray={`${2 * Math.PI * 56}`}
                    strokeDashoffset={`${2 * Math.PI * 56 * (1 - progress / 100)}`}
                    strokeLinecap="round"
                  />
                  <defs>
                    <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#06b6d4" />
                      <stop offset="50%" stopColor="#a855f7" />
                      <stop offset="100%" stopColor="#ec4899" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <motion.div
                    className="text-2xl font-bold text-white"
                    animate={{ scale: [1, 1.1, 1] }}
                    transition={{ duration: 1, repeat: Infinity }}
                  >
                    {Math.round(progress)}%
                  </motion.div>
                </div>
              </div>

              {/* Stage Labels */}
              <div className="w-full space-y-2">
                <div className="flex justify-between text-xs text-white/60">
                  <motion.span
                    animate={{ 
                      color: stage === "thinking" ? "#fbbf24" : "rgba(255, 255, 255, 0.4)",
                      fontWeight: stage === "thinking" ? "bold" : "normal"
                    }}
                  >
                    Thinking
                  </motion.span>
                  <motion.span
                    animate={{ 
                      color: stage === "generating" ? "#a855f7" : "rgba(255, 255, 255, 0.4)",
                      fontWeight: stage === "generating" ? "bold" : "normal"
                    }}
                  >
                    Generating
                  </motion.span>
                  <motion.span
                    animate={{ 
                      color: stage === "validating" ? "#4ade80" : "rgba(255, 255, 255, 0.4)",
                      fontWeight: stage === "validating" ? "bold" : "normal"
                    }}
                  >
                    Validating
                  </motion.span>
                  <motion.span
                    animate={{ 
                      color: stage === "ready" ? "#06b6d4" : "rgba(255, 255, 255, 0.4)",
                      fontWeight: stage === "ready" ? "bold" : "normal"
                    }}
                  >
                    Ready
                  </motion.span>
                </div>
              </div>

              {/* Status Message */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="text-center space-y-2"
              >
                <h3 className="text-lg font-bold text-white">
                  {stage === "thinking" && "Processing Query"}
                  {stage === "generating" && "Generating Response"}
                  {stage === "validating" && "Validating Answer"}
                  {stage === "ready" && "Answer Ready"}
                </h3>
                {message && (
                  <p className="text-sm text-white/70">{message}</p>
                )}
              </motion.div>

              {/* Typing Animation */}
              {stage === "generating" && (
                <div className="flex space-x-1">
                  {[0, 1, 2].map((i) => (
                    <motion.div
                      key={i}
                      className="w-3 h-3 bg-cyan-400 rounded-full"
                      animate={{
                        y: [0, -12, 0],
                        opacity: [0.4, 1, 0.4]
                      }}
                      transition={{
                        duration: 1.2,
                        repeat: Infinity,
                        delay: i * 0.2
                      }}
                    />
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
