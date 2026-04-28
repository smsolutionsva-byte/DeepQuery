import { motion, AnimatePresence } from "motion/react";
import { Brain, Cpu, Search, Zap, Network } from "lucide-react";

interface SystemAnalysisAnimationProps {
  isActive: boolean;
  stage: "scanning" | "analyzing" | "computing" | "complete";
  progress?: number;
  message?: string;
}

export default function SystemAnalysisAnimation({ 
  isActive, 
  stage, 
  progress = 0, 
  message 
}: SystemAnalysisAnimationProps) {
  return (
    <AnimatePresence>
      {isActive && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center z-50"
        >
          <motion.div
            initial={{ scale: 0.9, y: 20 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.9, y: 20 }}
            className="bg-gradient-to-br from-slate-900 to-slate-800 border border-purple-500/30 rounded-3xl p-8 max-w-lg w-full mx-4 shadow-2xl"
          >
            <div className="flex flex-col items-center space-y-6">
              {/* Animated Brain/Network Visualization */}
              <div className="relative w-32 h-32">
                {/* Central Brain */}
                <motion.div
                  className="absolute inset-0 flex items-center justify-center"
                  animate={{
                    scale: [1, 1.1, 1],
                    rotate: [0, 5, -5, 0]
                  }}
                  transition={{ duration: 3, repeat: Infinity }}
                >
                  <Brain className="w-20 h-20 text-purple-400" />
                </motion.div>

                {/* Orbiting Nodes */}
                {[0, 1, 2, 3, 4, 5].map((i) => (
                  <motion.div
                    key={i}
                    className="absolute w-4 h-4 bg-cyan-400 rounded-full"
                    style={{
                      top: "50%",
                      left: "50%",
                      transformOrigin: "0 0"
                    }}
                    animate={{
                      rotate: [0, 360],
                      x: [0, Math.cos((i * 60) * Math.PI / 180) * 60],
                      y: [0, Math.sin((i * 60) * Math.PI / 180) * 60],
                    }}
                    transition={{
                      duration: 4 + i * 0.5,
                      repeat: Infinity,
                      ease: "linear"
                    }}
                  >
                    <motion.div
                      animate={{ scale: [1, 1.5, 1] }}
                      transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
                    />
                  </motion.div>
                ))}

                {/* Connecting Lines */}
                <svg className="absolute inset-0 w-full h-full" style={{ transform: "rotate(-90deg)" }}>
                  {[0, 1, 2].map((i) => (
                    <motion.line
                      key={i}
                      x1="64"
                      y1="64"
                      x2="64"
                      y2="20"
                      stroke="rgba(147, 51, 234, 0.3)"
                      strokeWidth="2"
                      animate={{
                        rotate: [0, 360],
                        transformOrigin: "64px 64px"
                      }}
                      transition={{
                        duration: 3,
                        repeat: Infinity,
                        delay: i * 1
                      }}
                    />
                  ))}
                </svg>
              </div>

              {/* Stage Indicators */}
              <div className="flex items-center space-x-4">
                {stage === "scanning" && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  >
                    <Search className="w-6 h-6 text-blue-400" />
                  </motion.div>
                )}
                {stage === "analyzing" && (
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  >
                    <Cpu className="w-6 h-6 text-purple-400" />
                  </motion.div>
                )}
                {stage === "computing" && (
                  <motion.div
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 0.8, repeat: Infinity }}
                  >
                    <Zap className="w-6 h-6 text-yellow-400" />
                  </motion.div>
                )}
                {stage === "complete" && (
                  <motion.div
                    initial={{ scale: 0, rotate: -180 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{ duration: 0.6, type: "spring" }}
                  >
                    <Network className="w-6 h-6 text-green-400" />
                  </motion.div>
                )}
              </div>

              {/* Progress Visualization */}
              <div className="w-full space-y-3">
                <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-purple-500 via-cyan-400 to-blue-500"
                    initial={{ width: "0%" }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                  />
                </div>
                
                {/* Stage Labels */}
                <div className="flex justify-between text-xs text-slate-400">
                  <motion.span
                    animate={{ 
                      color: stage === "scanning" ? "#60a5fa" : "#64748b",
                      scale: stage === "scanning" ? 1.1 : 1
                    }}
                  >
                    Scanning
                  </motion.span>
                  <motion.span
                    animate={{ 
                      color: stage === "analyzing" ? "#a78bfa" : "#64748b",
                      scale: stage === "analyzing" ? 1.1 : 1
                    }}
                  >
                    Analyzing
                  </motion.span>
                  <motion.span
                    animate={{ 
                      color: stage === "computing" ? "#fbbf24" : "#64748b",
                      scale: stage === "computing" ? 1.1 : 1
                    }}
                  >
                    Computing
                  </motion.span>
                  <motion.span
                    animate={{ 
                      color: stage === "complete" ? "#4ade80" : "#64748b",
                      scale: stage === "complete" ? 1.1 : 1
                    }}
                  >
                    Complete
                  </motion.span>
                </div>
              </div>

              {/* Status Message */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="text-center space-y-2"
              >
                <h3 className="text-xl font-bold bg-gradient-to-r from-purple-300 to-cyan-300 bg-clip-text text-transparent">
                  {stage === "scanning" && "Scanning Vector Space"}
                  {stage === "analyzing" && "Analyzing Patterns"}
                  {stage === "computing" && "Computing Similarities"}
                  {stage === "complete" && "Analysis Complete"}
                </h3>
                {message && (
                  <p className="text-sm text-slate-400">{message}</p>
                )}
              </motion.div>

              {/* Particle Effects */}
              {stage === "computing" && (
                <div className="relative w-full h-16 overflow-hidden">
                  {[...Array(8)].map((_, i) => (
                    <motion.div
                      key={i}
                      className="absolute w-2 h-2 bg-cyan-400 rounded-full"
                      style={{
                        left: `${Math.random() * 100}%`,
                        bottom: 0
                      }}
                      animate={{
                        y: [0, -64, 0],
                        opacity: [0, 1, 0],
                        x: [0, (Math.random() - 0.5) * 40, 0]
                      }}
                      transition={{
                        duration: 2 + Math.random(),
                        repeat: Infinity,
                        delay: Math.random() * 2
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
