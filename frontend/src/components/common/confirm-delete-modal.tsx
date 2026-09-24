"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Loader2 } from "lucide-react";

interface ConfirmDeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void> | void;
  title?: string;
  description?: string;
  itemName?: string;
}

export function ConfirmDeleteModal({
  isOpen,
  onClose,
  onConfirm,
  title = "Confirm Deletion",
  description = "Are you sure you want to delete this item? This action will remove it from your Master Workspace and cannot be undone.",
  itemName,
}: ConfirmDeleteModalProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleConfirm = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err: any) {
      setDeleteError(err.message || "Failed to delete item. Please try again.");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={isDeleting ? () => {} : onClose}
      title={title}
      maxWidth="md"
    >
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-btn border border-status-error/20 bg-status-error-soft/30 p-3.5">
          <AlertTriangle className="h-5 w-5 text-status-error shrink-0 mt-0.5" />
          <div className="space-y-1 text-small">
            {itemName && (
              <p className="font-semibold text-primary">
                &ldquo;{itemName}&rdquo;
              </p>
            )}
            <p className="text-secondary">{description}</p>
          </div>
        </div>

        {deleteError && (
          <p className="text-small text-status-error font-medium">{deleteError}</p>
        )}

        <div className="flex justify-end gap-2.5 pt-2 border-t border-border/60">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={handleConfirm}
            disabled={isDeleting}
            className="bg-status-error hover:bg-status-error/90 text-white focus-visible:ring-status-error"
          >
            {isDeleting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                <span>Deleting...</span>
              </>
            ) : (
              <span>Delete</span>
            )}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
