"use client";
// components/Modal.tsx

import Modal from './Modal';
import { useEventState } from "../../context/EventStateContext";
import { ReactNode, useState, useEffect } from "react";

import axios from 'axios';
import { useAuth } from "~/context/AuthContext";
import { getAdminCategories } from '../utils/api/users';
import { CategoryOrg } from '../utils/types';

type ModalProps = {
  show: boolean;
  onClose: () => void;
};

export default function ModalUploadOne({ show, onClose }: ModalProps) {

  const [selectedOption, setSelectedOption] = useState<CategoryOrg | null>(null);
  const { isSignedIn } = useAuth();
  const [loading, setLoading] = useState<boolean>(true);
  const [adminCategories, setAdminCategories] = useState<CategoryOrg[]>([]);
  const { openUploadLink } = useEventState();

  useEffect(() => {
    const fetchAdminCategories = async () => {
      if (!isSignedIn) return;

      try {
        const categories = await getAdminCategories();
        if (categories) {
          setAdminCategories(categories);
        }
      } finally {
        setLoading(false);
      }
    };

    void fetchAdminCategories();
  }, [isSignedIn]);

  if (!isSignedIn) return null;

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg max-w-md w-full">
          <h2 className="text-lg font-semibold mb-4">Loading Calendars...</h2>
          <p className="text-gray-600 dark:text-gray-400">Please wait while we fetch your authorized calendars.</p>
        </div>
      </div>
    );
  }
  

  return (
    <Modal show={show} onClose={onClose}>
      <h2 className="text-lg font-semibold mb-4">Choose a calendar</h2>
      <select
        className="w-full border rounded-md p-2 mb-4"
        value={selectedOption?.id ?? ""}
        onChange={(e) => {
          const selected = adminCategories.find((cat) => String(cat.id) === e.target.value);
          setSelectedOption(selected ?? null);
        }}
      >
        <option value="" disabled>Select a calendar</option>
        {adminCategories.map((category) => (
          <option key={category.id} value={category.id}>
            {category.organization_name} - {category.name}
          </option>
        ))}
      </select>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        No available calendars? Please fill out this{" "}
        <a href='https://forms.gle/DaaShMuQpbYiSNLn6' target='_blank' className="text-blue-600 hover:underline">google form</a>{" "}
        to request edit access to an organization&apos;s calendar.
      </p>
      <button
        className="px-4 py-2 bg-blue-500 text-white rounded-md w-full disabled:opacity-50 disabled:cursor-not-allowed"
        disabled={!selectedOption}
        onClick={() => {
          if (selectedOption) {
            // setSelectedCategory(selectedOption);
            // setShowUploadModalOne(false);
            // setShowUploadModalTwo(true);
            openUploadLink(selectedOption);
          }
        }}
      >
        Next
      </button>
    </Modal>
  );
}
