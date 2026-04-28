import { motion, AnimatePresence } from "motion/react";
import { Database, Upload, CheckCircle, AlertCircle } from "lucide-react";

interface DataStorageAnimationProps {
  isActive: boolean;
  status: "uploading" | "processing" | "success" | "error";
  message?: string;
}

export default function DataStorageAnimation({ isActive, status, message }: DataStorageAnimationProps) {
  return (
    <AnimatePresence>
      {isActive && (
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
        >
          <motion.div
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 50, opacity: 0 }}
            className="bg-slate-900 border border-cyan-500/30 rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl"
          >
            <div className="flex flex-col items-center space-y-6">
              {/* Animated Database Icon */}
              <motion.div
                className="relative"
                animate={{
                  rotate: status === "processing" ? 360 : 0,
                }}
                transition={{
                  duration: 2,
                  repeat: status === "processing" ? Infinity : 0,
                  ease: "linear"
                }}
              >
                <Database className="w-16 h-16 text-cyan-400" />
                
                {/* Pulsing rings */}
                {status === "processing" && (
                  <>
                    <motion.div
                      className="absolute inset-0 border-2 border-cyan-400/30 rounded-full"
                      animate={{ scale: [1, 1.5, 2], opacity: [1, 0.5, 0] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    />
                    <motion.div
                      className="absolute inset-0 border-2 border-cyan-400/20 rounded-full"
                      animate={{ scale: [1, 1.5, 2], opacity: [1, 0.5, 0] }}
                      transition={{ duration: 2, repeat: Infinity, delay: 0.5 }}
                    />
                  </>
                )}
              </motion.div>

              {/* Status Icons */}
              <div className="flex items-center space-x-2">
                {status === "uploading" && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  >
                    <Upload className="w-6 h-6 text-blue-400" />
                  </motion.div>
                )}
                {status === "processing" && (
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 1, repeat: Infinity }}
                  >
                    <AlertCircle className="w-6 h-6 text-yellow-400" />
                  </motion.div>
                )}
                {status === "success" && (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: [0, 1.2, 1] }}
                    transition={{ duration: 0.5 }}
                  >
                    <CheckCircle className="w-6 h-6 text-green-400" />
                  </motion.div>
                )}
                {status === "error" && (
                  <motion.div
                    animate={{ x: [-5, 5, -5] }}
                    transition={{ duration: 0.3, repeat: 3 }}
                  >
                    <AlertCircle className="w-6 h-6 text-red-400" />
                  </motion.div>
                )}
              </div>

              {/* Progress Bar */}
              {status === "uploading" || status === "processing" ? (
                <div className="w-full space-y-2">
                  <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-cyan-400 to-blue-500"
                      initial={{ width: "0%" }}
                      animate={{ width: status === "uploading" ? "60%" : "90%" }}
                      transition={{ duration: 2, ease: "easeInOut" }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-slate-400">
                    <span>{status === "uploading" ? "Uploading data..." : "Processing vectors..."}</span>
                    <span>{status === "uploading" ? "60%" : "90%"}</span>
                  </div>
                </div>
              ) : null}

              {/* Status Message */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="text-center"
              >
                <h3 className="text-lg font-semibold text-cyan-300 mb-2">
                  {status === "uploading" && "Storing to Backend"}
                  {status === "processing" && "Processing Data"}
                  {status === "success" && "Data Stored Successfully"}
                  {status === "error" && "Storage Failed"}
                </h3>
                {message && (
                  <p className="text-sm text-slate-400">{message}</p>
                )}
              </motion.div>

              {/* Data Packets Animation */}
              {status === "processing" && (
                <div className="flex space-x-2">
                  {[0, 1, 2].map((i) => (
                    <motion.div
                      key={i}
                      className="w-3 h-3 bg-cyan-400 rounded-full"
                      animate={{
                        y: [0, -10, 0],
                        opacity: [0.5, 1, 0.5]
                      }}
                      transition={{
                        duration: 1,
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
