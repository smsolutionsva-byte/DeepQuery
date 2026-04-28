import { motion, AnimatePresence } from "motion/react";
import { Box, Layers, ArrowRight, Database, Sparkles, Cpu } from "lucide-react";

interface VectorCreationAnimationProps {
  isActive: boolean;
  stage: "encoding" | "vectorizing" | "cosine" | "storing";
  vectorData?: number[];
  progress?: number;
  message?: string;
}

export default function VectorCreationAnimation({ 
  isActive, 
  stage, 
  vectorData = [],
  progress = 0, 
  message 
}: VectorCreationAnimationProps) {
  return (
    <AnimatePresence>
      {isActive && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/80 backdrop-blur-xl flex items-center justify-center z-50"
        >
          <motion.div
            initial={{ scale: 0.7, rotateY: -20 }}
            animate={{ scale: 1, rotateY: 0 }}
            exit={{ scale: 0.7, rotateY: -20 }}
            className="bg-gradient-to-br from-emerald-900 via-teal-900 to-cyan-900 border border-emerald-400/40 rounded-3xl p-8 max-w-2xl w-full mx-4 shadow-2xl"
            style={{ perspective: "1000px" }}
          >
            <div className="flex flex-col items-center space-y-8">
              {/* Vector Visualization */}
              <div className="relative w-full h-48">
                {/* Input to Vector Transformation */}
                <div className="absolute inset-0 flex items-center justify-between px-8">
                  {/* Input Box */}
                  <motion.div
                    animate={{
                      scale: stage === "encoding" ? [1, 1.1, 1] : 1,
                      borderColor: stage === "encoding" ? "#10b981" : "rgba(255, 255, 255, 0.2)"
                    }}
                    className="w-20 h-20 border-2 border-white/20 rounded-lg flex items-center justify-center bg-white/5"
                  >
                    <Box className="w-10 h-10 text-emerald-400" />
                  </motion.div>

                  {/* Arrow */}
                  <motion.div
                    animate={{ x: [0, 10, 0] }}
                    transition={{ duration: 1, repeat: Infinity }}
                    className="flex-1 flex items-center justify-center"
                  >
                    <ArrowRight className="w-8 h-8 text-cyan-400" />
                  </motion.div>

                  {/* Vector Representation */}
                  <motion.div
                    animate={{
                      scale: stage === "vectorizing" ? [1, 1.1, 1] : 1,
                      borderColor: stage === "vectorizing" ? "#06b6d4" : "rgba(255, 255, 255, 0.2)"
                    }}
                    className="w-32 h-20 border-2 border-white/20 rounded-lg flex items-center justify-center bg-white/5 overflow-hidden"
                  >
                    <div className="flex space-x-1">
                      {vectorData.slice(0, 8).map((val, i) => (
                        <motion.div
                          key={i}
                          className="w-2 bg-cyan-400 rounded-full"
                          animate={{
                            height: [4, 20, 4],
                            opacity: [0.3, 1, 0.3]
                          }}
                          transition={{
                            duration: 2,
                            repeat: Infinity,
                            delay: i * 0.1
                          }}
                        />
                      ))}
                    </div>
                  </motion.div>

                  {/* Arrow */}
                  <motion.div
                    animate={{ x: [0, 10, 0] }}
                    transition={{ duration: 1, repeat: Infinity, delay: 0.5 }}
                    className="flex-1 flex items-center justify-center"
                  >
                    <ArrowRight className="w-8 h-8 text-purple-400" />
                  </motion.div>

                  {/* Cosine Similarity */}
                  <motion.div
                    animate={{
                      scale: stage === "cosine" ? [1, 1.1, 1] : 1,
                      borderColor: stage === "cosine" ? "#a855f7" : "rgba(255, 255, 255, 0.2)"
                    }}
                    className="w-24 h-20 border-2 border-white/20 rounded-lg flex items-center justify-center bg-white/5"
                  >
                    <Layers className="w-10 h-10 text-purple-400" />
                  </motion.div>

                  {/* Arrow */}
                  <motion.div
                    animate={{ x: [0, 10, 0] }}
                    transition={{ duration: 1, repeat: Infinity, delay: 1 }}
                    className="flex-1 flex items-center justify-center"
                  >
                    <ArrowRight className="w-8 h-8 text-green-400" />
                  </motion.div>

                  {/* Database Storage */}
                  <motion.div
                    animate={{
                      scale: stage === "storing" ? [1, 1.1, 1] : 1,
                      borderColor: stage === "storing" ? "#4ade80" : "rgba(255, 255, 255, 0.2)"
                    }}
                    className="w-20 h-20 border-2 border-white/20 rounded-lg flex items-center justify-center bg-white/5"
                  >
                    <Database className="w-10 h-10 text-green-400" />
                  </motion.div>
                </div>

                {/* Floating Particles */}
                {stage === "vectorizing" && [...Array(12)].map((_, i) => (
                  <motion.div
                    key={i}
                    className="absolute w-1 h-1 bg-cyan-400 rounded-full"
                    style={{
                      left: `${Math.random() * 100}%`,
                      top: `${Math.random() * 100}%`
                    }}
                    animate={{
                      y: [0, -30, 0],
                      x: [0, (Math.random() - 0.5) * 20, 0],
                      opacity: [0, 1, 0]
                    }}
                    transition={{
                      duration: 2 + Math.random() * 2,
                      repeat: Infinity,
                      delay: Math.random() * 2
                    }}
                  />
                ))}
              </div>

              {/* Stage Indicators */}
              <div className="flex items-center space-x-4">
                {stage === "encoding" && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                  >
                    <Cpu className="w-8 h-8 text-emerald-400" />
                  </motion.div>
                )}
                {stage === "vectorizing" && (
                  <motion.div
                    animate={{ scale: [1, 1.3, 1] }}
                    transition={{ duration: 1, repeat: Infinity }}
                  >
                    <Sparkles className="w-8 h-8 text-cyan-400" />
                  </motion.div>
                )}
                {stage === "cosine" && (
                  <motion.div
                    animate={{ rotate: [0, 180, 360] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                  >
                    <Layers className="w-8 h-8 text-purple-400" />
                  </motion.div>
                )}
                {stage === "storing" && (
                  <motion.div
                    initial={{ scale: 0, rotate: -180 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{ duration: 0.6, type: "spring" }}
                  >
                    <Database className="w-8 h-8 text-green-400" />
                  </motion.div>
                )}
              </div>

              {/* Vector Data Display */}
              {vectorData.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="w-full bg-black/30 rounded-xl p-4"
                >
                  <div className="text-xs text-emerald-400 mb-2">Vector Embedding (first 16 dimensions):</div>
                  <div className="grid grid-cols-8 gap-2 text-xs">
                    {vectorData.slice(0, 16).map((val, i) => (
                      <motion.div
                        key={i}
                        className="bg-emerald-900/50 text-emerald-300 rounded px-2 py-1 text-center font-mono"
                        animate={{
                          scale: [0.8, 1, 0.8],
                          opacity: [0.5, 1, 0.5]
                        }}
                        transition={{
                          duration: 2,
                          repeat: Infinity,
                          delay: i * 0.05
                        }}
                      >
                        {val.toFixed(3)}
                      </motion.div>
                    ))}
                  </div>
                </motion.div>
              )}

              {/* Progress Visualization */}
              <div className="w-full space-y-3">
                <div className="h-4 bg-black/30 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-emerald-500 via-cyan-500 to-purple-500"
                    initial={{ width: "0%" }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                  />
                </div>
                
                {/* Stage Labels */}
                <div className="flex justify-between text-xs text-white/60">
                  <motion.span
                    animate={{ 
                      color: stage === "encoding" ? "#10b981" : "rgba(255, 255, 255, 0.4)",
                      fontWeight: stage === "encoding" ? "bold" : "normal"
                    }}
                  >
                    Encoding
                  </motion.span>
                  <motion.span
                    animate={{ 
                      color: stage === "vectorizing" ? "#06b6d4" : "rgba(255, 255, 255, 0.4)",
                      fontWeight: stage === "vectorizing" ? "bold" : "normal"
                    }}
                  >
                    Vectorizing
                  </motion.span>
                  <motion.span
                    animate={{ 
                      color: stage === "cosine" ? "#a855f7" : "rgba(255, 255, 255, 0.4)",
                      fontWeight: stage === "cosine" ? "bold" : "normal"
                    }}
                  >
                    Cosine
                  </motion.span>
                  <motion.span
                    animate={{ 
                      color: stage === "storing" ? "#4ade80" : "rgba(255, 255, 255, 0.4)",
                      fontWeight: stage === "storing" ? "bold" : "normal"
                    }}
                  >
                    Storing
                  </motion.span>
                </div>
              </div>

              {/* Status Message */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                className="text-center space-y-2"
              >
                <h3 className="text-xl font-bold bg-gradient-to-r from-emerald-300 to-cyan-300 bg-clip-text text-transparent">
                  {stage === "encoding" && "Encoding Input Data"}
                  {stage === "vectorizing" && "Creating Vector Embeddings"}
                  {stage === "cosine" && "Computing Cosine Similarity"}
                  {stage === "storing" && "Storing in Vector Database"}
                </h3>
                {message && (
                  <p className="text-sm text-white/70">{message}</p>
                )}
              </motion.div>

              {/* Mathematical Visualization */}
              {stage === "cosine" && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="bg-black/40 rounded-xl p-4 text-center"
                >
                  <div className="text-emerald-400 font-mono text-sm">
                    cos(θ) = (A · B) / (||A|| × ||B||)
                  </div>
                  <div className="text-cyan-400 font-mono text-xs mt-2">
                    Similarity: {(0.85 + Math.random() * 0.14).toFixed(4)}
                  </div>
                </motion.div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
